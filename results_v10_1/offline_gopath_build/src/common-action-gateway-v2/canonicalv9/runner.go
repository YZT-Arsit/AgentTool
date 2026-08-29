package canonicalv9

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"

	gatewayv2 "common-action-gateway-v2"
	"common-action-gateway-v2/v7"
	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v8"
	"common-action-gateway-v2/v9ohttp"
	ohttp "github.com/chris-wood/ohttp-go"
)

type RouteSpec struct {
	RouteHandle     string `json:"route_handle"`
	ActionKind      string `json:"action_kind"`
	EffectSemantics string `json:"effect_semantics"`
	Endpoint        string `json:"endpoint"`
	PolicyID        string `json:"policy_id"`
}

type ActionSpec struct {
	OperationID        string `json:"operation_id"`
	ActionKind         string `json:"action_kind"`
	RouteHandle        string `json:"route_handle"`
	EffectSemantics    string `json:"effect_semantics"`
	PolicyID           string `json:"policy_id"`
	ProtectedArguments []byte `json:"protected_arguments"`
}

type Plan struct {
	ProfileID                 string       `json:"profile_id"`
	StateDirectory            string       `json:"state_directory"`
	Rounds                    int          `json:"rounds"`
	AdmissionRounds           int          `json:"admission_rounds"`
	MaximumRealOperations     int          `json:"maximum_real_operations"`
	RoundPeriodMS             int          `json:"round_period_ms"`
	ProviderCompletionBoundMS int          `json:"provider_completion_bound_ms"`
	RequestBHTTPBytes         int          `json:"request_bhttp_bytes"`
	ResponseBHTTPBytes        int          `json:"response_bhttp_bytes"`
	RequestFinalBytes         int          `json:"request_final_bytes"`
	ResponseFinalBytes        int          `json:"response_final_bytes"`
	Routes                    []RouteSpec  `json:"routes"`
	Actions                   []ActionSpec `json:"actions"`
}

type PrivateEvent struct {
	OperationID string `json:"operation_id,omitempty"`
	Stage       string `json:"stage"`
	ActionKind  string `json:"action_kind,omitempty"`
	RouteHandle string `json:"route_handle,omitempty"`
	Status      string `json:"status,omitempty"`
	Round       int    `json:"round,omitempty"`
}

type ClientResult struct {
	OperationID string `json:"operation_id"`
	Status      byte   `json:"status"`
	Payload     []byte `json:"payload"`
	Round       int    `json:"round"`
}

type RunResult struct {
	ProfileID               string                `json:"profile_id"`
	Rounds                  int                   `json:"rounds"`
	Admitted                int                   `json:"admitted"`
	ProviderInvocations     int64                 `json:"provider_invocations"`
	DummyProviderOperations int64                 `json:"dummy_provider_operations"`
	ProfileOverflowEvents   int                   `json:"profile_overflow_events"`
	Results                 []ClientResult        `json:"results"`
	PrivateEvents           []PrivateEvent        `json:"private_events"`
	PublicRelayEvents       []v8.RelayPublicEvent `json:"public_relay_events"`
	AfterCutoffOperations   []string              `json:"after_cutoff_operations"`
	RequestFinalBytes       int                   `json:"request_final_bytes"`
	ResponseFinalBytes      int                   `json:"response_final_bytes"`
}

type providerRequest struct {
	OperationID string `json:"operation_id"`
	Payload     []byte `json:"payload"`
}

type providerResponse struct {
	Status  string `json:"status"`
	Payload []byte `json:"payload"`
}

type engine struct {
	plan          Plan
	codec         v9ohttp.RFC9292Codec
	client        *v9ohttp.RFC9458Client
	gateway       *v9ohttp.RFC9458Gateway
	routes        map[string]RouteSpec
	journal       *v7.EffectRecoveryJournal
	ready         *v7.DurableReadyQueue
	memory        *v8.MemoryDeliveryQueue
	httpClient    *http.Client
	round         atomic.Uint32
	providerCalls atomic.Int64
	eventsMu      sync.Mutex
	events        []PrivateEvent
	workers       sync.WaitGroup
}

func effect(value string) (gatewayv2.EffectSemantics, error) {
	switch value {
	case string(gatewayv2.ReadOnly):
		return gatewayv2.ReadOnly, nil
	case string(gatewayv2.IdempotentEffect):
		return gatewayv2.IdempotentEffect, nil
	case string(gatewayv2.NonIdempotentEffect):
		return gatewayv2.NonIdempotentEffect, nil
	default:
		return "", fmt.Errorf("unknown effect semantics %q", value)
	}
}

func actionKind(value string) (v7ohttp.ActionKind, error) {
	switch value {
	case string(v7ohttp.ActionRealTool):
		return v7ohttp.ActionRealTool, nil
	case string(v7ohttp.ActionAgentService):
		return v7ohttp.ActionAgentService, nil
	case string(v7ohttp.ActionExternalHTTP):
		return v7ohttp.ActionExternalHTTP, nil
	default:
		return "", fmt.Errorf("unsupported canonical action kind %q", value)
	}
}

func validateLoopback(endpoint string) error {
	parsed, err := url.Parse(endpoint)
	if err != nil || parsed.Scheme != "http" {
		return errors.New("canonical provider requires local HTTP endpoint")
	}
	host := parsed.Hostname()
	ip := net.ParseIP(host)
	if host != "localhost" && (ip == nil || !ip.IsLoopback()) {
		return errors.New("canonical provider endpoint is not loopback")
	}
	return nil
}

func validatePlan(plan Plan) error {
	if plan.ProfileID == "" || plan.StateDirectory == "" || plan.Rounds < 1 || plan.RoundPeriodMS < 1 {
		return errors.New("incomplete canonical plan")
	}
	if plan.RequestBHTTPBytes < 1 || plan.ResponseBHTTPBytes < 1 ||
		plan.RequestFinalBytes < 1 || plan.ResponseFinalBytes < 1 {
		return errors.New("canonical plan omits fixed wire sizes")
	}
	if len(plan.Actions) > plan.MaximumRealOperations || plan.AdmissionRounds < len(plan.Actions) {
		return errors.New("actions exceed public admission bound")
	}
	seenRoutes := make(map[string]bool)
	for _, route := range plan.Routes {
		if route.RouteHandle == "" || route.PolicyID == "" || seenRoutes[route.RouteHandle] {
			return errors.New("invalid or duplicate private route handle")
		}
		seenRoutes[route.RouteHandle] = true
		if _, err := actionKind(route.ActionKind); err != nil {
			return err
		}
		if _, err := effect(route.EffectSemantics); err != nil {
			return err
		}
		if err := validateLoopback(route.Endpoint); err != nil {
			return err
		}
	}
	for _, action := range plan.Actions {
		if action.OperationID == "" || !seenRoutes[action.RouteHandle] {
			return errors.New("action uses absent private route")
		}
	}
	return nil
}

func (e *engine) record(event PrivateEvent) {
	e.eventsMu.Lock()
	defer e.eventsMu.Unlock()
	e.events = append(e.events, event)
}

func resultRecord(operationID string, status byte, payload []byte) gatewayv2.ResultRecord {
	if len(payload) > gatewayv2.ResultPayloadBytes {
		payload = payload[:gatewayv2.ResultPayloadBytes]
	}
	result := gatewayv2.ResultRecord{Status: status, OperationID: gatewayv2.OperationID(operationID), PayloadLen: uint16(len(payload))}
	copy(result.Payload[:], payload)
	return result
}

func (e *engine) execute(route RouteSpec, action v7ohttp.PrivateActionMessage, currentRound uint32) {
	defer e.workers.Done()
	operationID := string(action.OperationID)
	e.providerCalls.Add(1)
	e.record(PrivateEvent{OperationID: operationID, Stage: "PROVIDER_CALL_BEGIN", ActionKind: string(action.Kind), RouteHandle: route.RouteHandle, Round: int(currentRound)})
	body, _ := json.Marshal(providerRequest{OperationID: operationID, Payload: action.ProtectedArgs})
	request, _ := http.NewRequestWithContext(context.Background(), http.MethodPost, route.Endpoint, bytes.NewReader(body))
	request.Header.Set("Content-Type", "application/json")
	response, err := e.httpClient.Do(request)
	status := gatewayv2.StatusError
	var payload []byte
	if err == nil {
		defer response.Body.Close()
		var decoded providerResponse
		if response.StatusCode/100 == 2 && json.NewDecoder(io.LimitReader(response.Body, gatewayv2.ResultPayloadBytes+1024)).Decode(&decoded) == nil && decoded.Status == "OK" {
			status = gatewayv2.StatusOK
			payload = decoded.Payload
		}
	}
	result := resultRecord(operationID, status, payload)
	if err := e.journal.Commit(operationID, result); err != nil {
		e.record(PrivateEvent{OperationID: operationID, Stage: "RESULT_COMMIT_FAILED", Status: err.Error()})
		return
	}
	e.record(PrivateEvent{OperationID: operationID, Stage: "RESULT_COMMITTED", Status: fmt.Sprintf("%d", status)})
	if _, err := e.ready.Enqueue(result, time.Now().UnixNano()); err != nil {
		e.record(PrivateEvent{OperationID: operationID, Stage: "READY_PUBLICATION_FAILED", Status: err.Error()})
		return
	}
	e.record(PrivateEvent{OperationID: operationID, Stage: "READY_PUBLISHED"})
}

func (e *engine) accept(action v7ohttp.PrivateActionMessage, currentRound uint32) error {
	if action.Kind == v7ohttp.ActionNoop {
		return nil
	}
	route, ok := e.routes[string(action.RouteHandle)]
	if !ok {
		return errors.New("private route handle not present in trusted Gateway map")
	}
	if route.ActionKind != string(action.Kind) {
		return errors.New("private action kind does not match trusted route")
	}
	var authorization struct {
		EffectSemantics string `json:"effect_semantics"`
		PolicyID        string `json:"policy_id"`
	}
	if json.Unmarshal(action.Authorization, &authorization) != nil ||
		authorization.EffectSemantics != route.EffectSemantics || authorization.PolicyID != route.PolicyID {
		return errors.New("private authorization metadata does not match trusted route")
	}
	semantics, _ := effect(route.EffectSemantics)
	operationID := string(action.OperationID)
	if err := e.journal.Accept(operationID, semantics); err != nil {
		return err
	}
	decision, committed, err := e.journal.Recover(operationID)
	if err != nil {
		return err
	}
	e.record(PrivateEvent{OperationID: operationID, Stage: "ACCEPTED", ActionKind: string(action.Kind), RouteHandle: route.RouteHandle, Round: int(currentRound)})
	switch decision {
	case v7.RecoveryReturnResult:
		if _, err := e.ready.Enqueue(committed, time.Now().UnixNano()); err != nil {
			return err
		}
		e.record(PrivateEvent{OperationID: operationID, Stage: "RECOVERY_COMMITTED_RESULT_REPUBLISHED"})
		return nil
	case v7.RecoveryOutcomeUnknown:
		ambiguous := resultRecord(operationID, gatewayv2.StatusAmbiguous, nil)
		if err := e.journal.Commit(operationID, ambiguous); err != nil {
			return err
		}
		if _, err := e.ready.Enqueue(ambiguous, time.Now().UnixNano()); err != nil {
			return err
		}
		e.record(PrivateEvent{OperationID: operationID, Stage: "RECOVERY_EFFECT_OUTCOME_UNKNOWN"})
		return nil
	case v7.RecoveryExecute:
		// A fresh operation transitions ACCEPTED -> PROVIDER_STARTED. On a
		// restart, READ_ONLY or explicitly idempotent work may already be in
		// PROVIDER_STARTED; Recover authorizes replay with the same operation ID.
		if err := e.journal.MarkProviderStarted(operationID); err != nil {
			if semantics == gatewayv2.NonIdempotentEffect {
				return errors.New("non-idempotent provider restart was not converted to outcome unknown")
			}
			e.record(PrivateEvent{OperationID: operationID, Stage: "RECOVERY_PROVIDER_RETRY_AUTHORIZED"})
		} else {
			e.record(PrivateEvent{OperationID: operationID, Stage: "PROVIDER_STARTED_DURABLE"})
		}
	default:
		return errors.New("unknown canonical recovery decision")
	}
	e.workers.Add(1)
	go e.execute(route, action, currentRound)
	return nil
}

func privateResponse(record *gatewayv2.ResultRecord) v7ohttp.PrivateResponse {
	if record == nil {
		return v7ohttp.PrivateResponse{Status: v9ohttp.StatusWait}
	}
	status := v9ohttp.StatusError
	switch record.Status {
	case gatewayv2.StatusOK:
		status = v9ohttp.StatusResult
	case gatewayv2.StatusTimeout:
		status = v9ohttp.StatusTimeout
	case gatewayv2.StatusAmbiguous:
		status = v9ohttp.StatusEffectOutcomeUnknown
	}
	return v7ohttp.PrivateResponse{Status: status, OperationID: gatewayv2.OperationIDString(record.OperationID), Payload: append([]byte(nil), record.Payload[:record.PayloadLen]...)}
}

func (e *engine) gatewayHandler(writer http.ResponseWriter, request *http.Request) {
	currentRound := e.round.Add(1)
	body, err := io.ReadAll(io.LimitReader(request.Body, int64(e.plan.RequestFinalBytes+1)))
	if err != nil || len(body) != e.plan.RequestFinalBytes {
		http.Error(writer, "invalid OHTTP request", http.StatusBadRequest)
		return
	}
	slot := v7ohttp.SlotID{Session: 1, Slot: currentRound}
	plaintext, responseContext, err := e.gateway.DecapsulateRequest(slot, body)
	if err != nil {
		http.Error(writer, "OHTTP decapsulation failed", http.StatusBadRequest)
		return
	}
	if responseContext.Slot() != slot {
		http.Error(writer, "OHTTP server context slot mismatch", http.StatusInternalServerError)
		return
	}
	_, action, err := e.codec.DecodeKnownLengthRequest(plaintext)
	if err != nil || e.accept(action, currentRound) != nil {
		http.Error(writer, "private action rejected", http.StatusBadRequest)
		return
	}
	selected, err := e.ready.ReserveEligible(1, currentRound)
	if err != nil {
		http.Error(writer, "ready-result selection failed", http.StatusInternalServerError)
		return
	}
	// All durable queue work is complete before the in-memory preparation
	// boundary.  The public preparation path snapshots only the bounded V8
	// memory queue, then encodes one immutable response.
	if selected != nil {
		if err := e.memory.PublishDurable(*selected); err != nil {
			http.Error(writer, "bounded ready-result publication failed", http.StatusInternalServerError)
			return
		}
	}
	preparedResult := e.memory.SnapshotEligible(1)
	bhttpResponse, err := e.codec.EncodeKnownLengthResponse(privateResponse(preparedResult), e.plan.ResponseBHTTPBytes)
	if err != nil {
		http.Error(writer, "BHTTP response failed", http.StatusInternalServerError)
		return
	}
	wire, err := e.gateway.EncapsulateResponse(responseContext, bhttpResponse)
	if err != nil || len(wire) != e.plan.ResponseFinalBytes {
		http.Error(writer, "OHTTP response failed", http.StatusInternalServerError)
		return
	}
	ack := make(chan string, 1)
	operationID := ""
	if preparedResult != nil {
		operationID = gatewayv2.OperationIDString(preparedResult.OperationID)
	}
	prepared := v8.PreparedSlot{Frame: wire, OperationID: operationID, Ack: ack}
	writer.Header().Set("Content-Type", v8.OHTTPResponseContentType)
	writer.Header().Set("Content-Length", fmt.Sprintf("%d", len(wire)))
	writer.WriteHeader(http.StatusOK)
	if err := prepared.Send(writer); err != nil {
		return
	}
	if operationID != "" {
		go func() {
			<-ack
			_ = e.ready.MarkDelivered(operationID)
			_ = e.journal.MarkResultDelivered(operationID)
			e.record(PrivateEvent{OperationID: operationID, Stage: "GATEWAY_DELIVERY_ACK_DURABLE", Round: int(currentRound)})
		}()
	}
}

func newEngine(plan Plan) (*engine, error) {
	if err := validatePlan(plan); err != nil {
		return nil, err
	}
	private, err := ohttp.NewConfig(7, 0x0020, 0x0001, 0x0001)
	if err != nil {
		return nil, err
	}
	suite := v9ohttp.PublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001, ConfigurationEpoch: 3, AuthenticatedSource: "V9_CANONICAL_LOCAL"}
	client, err := v9ohttp.NewRFC9458Client(private.Config(), suite)
	if err != nil {
		return nil, err
	}
	gateway, err := v9ohttp.NewRFC9458Gateway(private, suite)
	if err != nil {
		return nil, err
	}
	journal, err := v7.OpenEffectRecoveryJournal(filepath.Join(plan.StateDirectory, "effect_recovery.json"))
	if err != nil {
		return nil, err
	}
	ready, err := v7.OpenDurableReadyQueue(filepath.Join(plan.StateDirectory, "ready_results.json"), plan.MaximumRealOperations+1)
	if err != nil {
		return nil, err
	}
	memory, err := v8.NewMemoryDeliveryQueue(plan.MaximumRealOperations + 1)
	if err != nil {
		return nil, err
	}
	routes := make(map[string]RouteSpec)
	for _, route := range plan.Routes {
		routes[route.RouteHandle] = route
	}
	return &engine{plan: plan, codec: v9ohttp.RFC9292Codec{}, client: client, gateway: gateway,
		routes: routes, journal: journal, ready: ready, memory: memory,
		httpClient: &http.Client{Timeout: time.Duration(plan.ProviderCompletionBoundMS) * time.Millisecond}}, nil
}

func bindAdmission(plan Plan) error {
	profile, admission := canonicalProfiles(plan)
	return v8.BindAdmission(profile, admission)
}

func Run(plan Plan) (RunResult, error) {
	if err := bindAdmission(plan); err != nil {
		return RunResult{}, err
	}
	if err := os.MkdirAll(plan.StateDirectory, 0o700); err != nil {
		return RunResult{}, err
	}
	engine, err := newEngine(plan)
	if err != nil {
		return RunResult{}, err
	}
	gatewayServer := httptest.NewServer(http.HandlerFunc(engine.gatewayHandler))
	defer gatewayServer.Close()
	relayProfile := v8.ScheduleProfile{ProfileID: plan.ProfileID, Sessions: 1, SlotsPerSession: plan.Rounds,
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes,
		RequestIntervalNS:         int64(time.Duration(plan.RoundPeriodMS) * time.Millisecond),
		ResponseSlotIntervalNS:    int64(time.Duration(plan.RoundPeriodMS) * time.Millisecond),
		PublicLifetimeNS:          int64(time.Duration(plan.Rounds*plan.RoundPeriodMS) * time.Millisecond),
		MaximumAdmittedOperations: plan.MaximumRealOperations, TerminalSlots: 1,
		ProviderCompletionBoundNS: int64(time.Duration(plan.ProviderCompletionBoundMS) * time.Millisecond),
		RelayEndpoint:             "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY", ConnectionPolicy: "KEEP_ALIVE",
		OHTTPSuite: v8.OHTTPPublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001, ConfigEpoch: 3}}
	relay, err := v8.NewFreshRequestRelay(relayProfile, gatewayServer.URL)
	if err != nil {
		return RunResult{}, err
	}
	relayServer := httptest.NewServer(relay)
	defer relayServer.Close()

	clientHTTP := relayServer.Client()
	results := make([]ClientResult, 0, len(plan.Actions))
	start := time.Now()
	for round := 1; round <= plan.Rounds; round++ {
		deadline := start.Add(time.Duration(round-1) * time.Duration(plan.RoundPeriodMS) * time.Millisecond)
		if remaining := time.Until(deadline); remaining > 0 {
			time.Sleep(remaining)
		}
		message := v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionNoop, OperationID: []byte(fmt.Sprintf("noop-%06d", round))}
		if round <= len(plan.Actions) {
			action := plan.Actions[round-1]
			kind, _ := actionKind(action.ActionKind)
			authorization, _ := json.Marshal(map[string]string{"effect_semantics": action.EffectSemantics, "policy_id": action.PolicyID})
			message = v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: kind,
				RouteHandle: []byte(action.RouteHandle), OperationID: []byte(action.OperationID),
				ProtectedArgs: action.ProtectedArguments, Authorization: authorization}
		}
		bhttpRequest, err := engine.codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, message, plan.RequestBHTTPBytes)
		if err != nil {
			return RunResult{}, err
		}
		slot := v7ohttp.SlotID{Session: 1, Slot: uint32(round)}
		wire, responseContext, err := engine.client.EncapsulateRequest(slot, bhttpRequest)
		if err != nil || len(wire) != plan.RequestFinalBytes {
			return RunResult{}, errors.New("canonical request final size mismatch")
		}
		if responseContext.Slot() != slot {
			return RunResult{}, errors.New("OHTTP client context slot mismatch")
		}
		request, _ := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(wire))
		request.Header.Set("Content-Type", v8.OHTTPRequestContentType)
		request.Header.Set("X-Public-Round", fmt.Sprintf("%d", round))
		request.ContentLength = int64(len(wire))
		response, err := clientHTTP.Do(request)
		if err != nil {
			return RunResult{}, err
		}
		responseWire, readErr := io.ReadAll(response.Body)
		response.Body.Close()
		if readErr != nil || len(responseWire) != plan.ResponseFinalBytes {
			return RunResult{}, errors.New("canonical response final size mismatch")
		}
		opened, err := engine.client.DecapsulateResponse(responseContext, responseWire)
		if err != nil {
			return RunResult{}, err
		}
		decoded, err := engine.codec.DecodeKnownLengthResponse(opened)
		if err != nil {
			return RunResult{}, err
		}
		if decoded.Status != v9ohttp.StatusWait {
			results = append(results, ClientResult{OperationID: decoded.OperationID, Status: decoded.Status, Payload: decoded.Payload, Round: round})
			engine.record(PrivateEvent{OperationID: decoded.OperationID, Stage: "CLIENT_BHTTP_DECODED", Status: fmt.Sprintf("%d", decoded.Status), Round: round})
		}
	}
	engine.workers.Wait()
	deadline := time.Now().Add(2 * time.Second)
	for engine.ready.Pending() > 0 && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	return RunResult{ProfileID: plan.ProfileID, Rounds: plan.Rounds, Admitted: len(plan.Actions),
		ProviderInvocations: engine.providerCalls.Load(), DummyProviderOperations: 0,
		Results: results, PrivateEvents: append([]PrivateEvent(nil), engine.events...),
		PublicRelayEvents: relay.Events(), AfterCutoffOperations: []string{"wait", "PreparedSlot.Send", "one fixed-size writer.Write", "byte-count validation", "non-blocking in-memory acknowledgement"},
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes}, nil
}
