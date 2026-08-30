package canonicalv9

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"sort"
	"strconv"
	"sync"
	"time"

	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v8"
	"common-action-gateway-v2/v9ohttp"
)

// OnlineControlMessage is the trusted local IPC protocol. It is deliberately
// separate from the Relay-visible transport.
type OnlineControlMessage struct {
	Type   string      `json:"type"`
	Action *ActionSpec `json:"action,omitempty"`
}

type OnlineControlEvent struct {
	Type        string        `json:"type"`
	OperationID string        `json:"operation_id,omitempty"`
	Reason      string        `json:"reason,omitempty"`
	Round       int           `json:"round,omitempty"`
	Result      *ClientResult `json:"result,omitempty"`
}

type onlineEmitter struct {
	mu      sync.Mutex
	encoder *json.Encoder
}

func (e *onlineEmitter) emit(value OnlineControlEvent) {
	e.mu.Lock()
	defer e.mu.Unlock()
	_ = e.encoder.Encode(value)
}

type onlinePreparedRequest struct {
	slot        v7ohttp.SlotID
	wire        []byte
	context     v7ohttp.ClientContext
	operationID string
	real        bool
}

type onlineSlotState struct {
	mu        sync.Mutex
	deadline  time.Time
	cutoff    time.Time
	committed bool
	noop      onlinePreparedRequest
	real      *onlinePreparedRequest
}

// onlinePublicStartLeadPeriods is a public, secret-independent setup budget.
// It gives a pinned framework enough time to reach its first native outbound
// action after SESSION_READY without consuming the H50 admission window.  It
// does not change the 111-slot public lifetime and cannot be extended by
// private work or result readiness.
const onlinePublicStartLeadPeriods = 50

func actionMessage(action ActionSpec) (v7ohttp.PrivateActionMessage, error) {
	kind, err := actionKind(action.ActionKind)
	if err != nil {
		return v7ohttp.PrivateActionMessage{}, err
	}
	authorization, err := json.Marshal(map[string]string{
		"effect_semantics": action.EffectSemantics,
		"policy_id":        action.PolicyID,
	})
	if err != nil {
		return v7ohttp.PrivateActionMessage{}, err
	}
	return v7ohttp.PrivateActionMessage{
		ProtocolVersion: 1,
		Kind:            kind,
		RouteHandle:     []byte(action.RouteHandle),
		OperationID:     []byte(action.OperationID),
		ProtectedArgs:   action.ProtectedArguments,
		Authorization:   authorization,
	}, nil
}

func prepareOnlineRequest(engine *engine, plan Plan, slot v7ohttp.SlotID,
	message v7ohttp.PrivateActionMessage, operationID string, real bool) (onlinePreparedRequest, error) {
	bhttpRequest, err := engine.codec.EncodeKnownLengthRequestBound(
		v7ohttp.InnerSemanticTarget, message, plan.RequestBHTTPBytes, slot,
	)
	if err != nil {
		return onlinePreparedRequest{}, err
	}
	wire, responseContext, err := engine.client.EncapsulateRequest(slot, bhttpRequest)
	if err != nil || len(wire) != plan.RequestFinalBytes {
		return onlinePreparedRequest{}, errors.New("online canonical request final size mismatch")
	}
	if responseContext.Slot() != slot {
		return onlinePreparedRequest{}, errors.New("online OHTTP client context slot mismatch")
	}
	return onlinePreparedRequest{slot: slot, wire: wire, context: responseContext,
		operationID: operationID, real: real}, nil
}

func validateOnlineAction(plan Plan, routes map[string]RouteSpec, action ActionSpec) error {
	if action.OperationID == "" {
		return errors.New("online action has empty operation ID")
	}
	route, ok := routes[action.RouteHandle]
	if !ok {
		return errors.New("online action uses absent private route")
	}
	if route.ActionKind != action.ActionKind || route.EffectSemantics != action.EffectSemantics || route.PolicyID != action.PolicyID {
		return errors.New("online action disagrees with trusted route table")
	}
	if len(action.ProtectedArguments) > plan.RequestBHTTPBytes {
		return errors.New("online protected arguments exceed fixed request capacity")
	}
	return nil
}

// RunOnline runs one fixed public session while accepting future actions over
// trusted local IPC. The startup Plan must not contain an action sequence.
func RunOnline(plan Plan, controlIn io.Reader, controlOut io.Writer) (RunResult, error) {
	if len(plan.Actions) != 0 {
		return RunResult{}, errors.New("online mode forbids future actions in the startup plan")
	}
	if plan.PreparationLeadMS <= 0 || plan.PreparationLeadMS >= plan.RoundPeriodMS {
		return RunResult{}, errors.New("online preparation lead must be public and strictly below the round period")
	}
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
	emitter := &onlineEmitter{encoder: json.NewEncoder(controlOut)}
	processClock := time.Now()
	monotonicNS := func() int64 { return time.Since(processClock).Nanoseconds() }
	setupEvents := []PublicSetupEvent{{Stage: "GATEWAY_INSTANTIATED", MonotonicNS: monotonicNS()}}

	gatewayMux := http.NewServeMux()
	gatewayMux.HandleFunc("/preconnect", func(writer http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet || request.ProtoMajor != 2 {
			http.Error(writer, "canonical Gateway HTTP/2 preconnect rejected", http.StatusHTTPVersionNotSupported)
			return
		}
		writer.WriteHeader(http.StatusNoContent)
	})
	gatewayMux.HandleFunc("/", engine.gatewayHandler)
	gatewayServer := httptest.NewUnstartedServer(gatewayMux)
	gatewayServer.EnableHTTP2 = true
	gatewayServer.StartTLS()
	defer gatewayServer.Close()
	setupEvents = append(setupEvents, PublicSetupEvent{Stage: "GATEWAY_READY", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"})

	relayProfile := v8.ScheduleProfile{ProfileID: plan.ProfileID, Sessions: 1, SlotsPerSession: plan.Rounds,
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes,
		RequestIntervalNS:         int64(time.Duration(plan.RoundPeriodMS) * time.Millisecond),
		ResponseSlotIntervalNS:    int64(time.Duration(plan.RoundPeriodMS) * time.Millisecond),
		PublicLifetimeNS:          int64(time.Duration(plan.Rounds*plan.RoundPeriodMS) * time.Millisecond),
		MaximumAdmittedOperations: plan.MaximumRealOperations, TerminalSlots: 1,
		ProviderCompletionBoundNS: int64(time.Duration(plan.ProviderCompletionBoundMS) * time.Millisecond),
		RelayEndpoint:             "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY", ConnectionPolicy: "KEEP_ALIVE",
		OHTTPSuite: v8.OHTTPPublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001, ConfigEpoch: 3}}
	relay, err := v8.NewFreshRequestRelayWithClient(relayProfile, gatewayServer.URL, gatewayServer.Client(), true)
	if err != nil {
		return RunResult{}, err
	}
	relayServer := httptest.NewUnstartedServer(relay)
	relayServer.EnableHTTP2 = true
	relayServer.StartTLS()
	defer relayServer.Close()
	setupEvents = append(setupEvents, PublicSetupEvent{Stage: "RELAY_READY", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"})
	clientHTTP := relayServer.Client()
	preconnectRequest, _ := http.NewRequest(http.MethodGet, relayServer.URL+"/preconnect", nil)
	preconnectResponse, err := clientHTTP.Do(preconnectRequest)
	if err != nil {
		return RunResult{}, fmt.Errorf("PUBLIC_PRECONNECT failed: %w", err)
	}
	preconnectProto := preconnectResponse.Proto
	preconnectResponse.Body.Close()
	complete, clientH2, gatewayH2 := relay.PreconnectStatus()
	if preconnectResponse.StatusCode != http.StatusNoContent || preconnectProto != "HTTP/2.0" || !complete || !clientH2 || !gatewayH2 {
		return RunResult{}, errors.New("PUBLIC_PRECONNECT did not establish both HTTP/2 hops")
	}
	setupEvents = append(setupEvents,
		PublicSetupEvent{Stage: "CLIENT_RELAY_HTTP2_ESTABLISHED", MonotonicNS: monotonicNS(), HTTPVersion: preconnectProto},
		PublicSetupEvent{Stage: "RELAY_GATEWAY_HTTP2_ESTABLISHED", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"},
		PublicSetupEvent{Stage: "PUBLIC_SETUP_COMPLETE", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"},
	)

	period := time.Duration(plan.RoundPeriodMS) * time.Millisecond
	lead := time.Duration(plan.PreparationLeadMS) * time.Millisecond
	// A public start lead gives the trusted framework time to receive
	// SESSION_READY. It is fixed and independent of future action availability.
	t0 := time.Now().Add(onlinePublicStartLeadPeriods * period)
	slots := make([]*onlineSlotState, plan.Rounds)
	for index := range slots {
		slotID := v7ohttp.SlotID{Session: 1, Slot: uint32(index + 1)}
		message := v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionNoop,
			OperationID: []byte(fmt.Sprintf("noop-%06d", index+1))}
		noop, err := prepareOnlineRequest(engine, plan, slotID, message, "", false)
		if err != nil {
			return RunResult{}, err
		}
		deadline := t0.Add(time.Duration(index) * period)
		slots[index] = &onlineSlotState{deadline: deadline, cutoff: deadline.Add(-lead), noop: noop}
	}
	setupEvents = append(setupEvents,
		PublicSetupEvent{Stage: "PREBUILT_NOOP_TABLE_COMPLETE", MonotonicNS: monotonicNS()},
		PublicSetupEvent{Stage: "T0_ASSIGNED", MonotonicNS: monotonicNS()},
	)

	incoming := make(chan ActionSpec, plan.MaximumRealOperations+1)
	done := make(chan struct{})
	var acceptedMu sync.Mutex
	acceptedIDs := make([]string, 0, plan.MaximumRealOperations)
	resolvedNotAdmitted := make([]string, 0)
	seenOperations := make(map[string]bool)
	controlSubmitted := 0
	go func() {
		decoder := json.NewDecoder(bufio.NewReader(controlIn))
		for {
			var message OnlineControlMessage
			if err := decoder.Decode(&message); err != nil {
				return
			}
			if message.Type != "SUBMIT_RESOLVED_ACTION" || message.Action == nil {
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", Reason: "invalid trusted control message"})
				continue
			}
			action := *message.Action
			if err := validateOnlineAction(plan, engine.routes, action); err != nil {
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: err.Error()})
				continue
			}
			acceptedMu.Lock()
			duplicate := seenOperations[action.OperationID]
			if !duplicate {
				seenOperations[action.OperationID] = true
				controlSubmitted++
			}
			overCapacity := controlSubmitted > plan.MaximumRealOperations
			acceptedMu.Unlock()
			if duplicate || overCapacity {
				reason := "duplicate operation ID"
				if overCapacity {
					reason = "PROFILE_CAPACITY_EXCEEDED"
				}
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: reason})
				continue
			}
			select {
			case incoming <- action:
			case <-done:
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: "SESSION_CLOSED"})
				return
			}
		}
	}()

	// One trusted preparation worker preserves causal arrival order. It assigns
	// a private action only to a still-future public admission slot. Unused
	// candidate OHTTP contexts are discarded and never reused.
	go func() {
		nextSlot := 0
		for {
			select {
			case action := <-incoming:
				admitted := false
				for nextSlot < plan.AdmissionRounds {
					index := nextSlot
					nextSlot++
					state := slots[index]
					if !time.Now().Before(state.cutoff) {
						continue
					}
					message, err := actionMessage(action)
					if err != nil {
						break
					}
					candidate, err := prepareOnlineRequest(engine, plan, state.noop.slot, message, action.OperationID, true)
					if err != nil {
						break
					}
					state.mu.Lock()
					if !state.committed && time.Now().Before(state.cutoff) {
						state.real = &candidate
						admitted = true
					}
					state.mu.Unlock()
					if admitted {
						acceptedMu.Lock()
						acceptedIDs = append(acceptedIDs, action.OperationID)
						acceptedMu.Unlock()
						emitter.emit(OnlineControlEvent{Type: "ACTION_ACCEPTED", OperationID: action.OperationID, Round: index + 1})
						break
					}
				}
				if !admitted {
					acceptedMu.Lock()
					resolvedNotAdmitted = append(resolvedNotAdmitted, action.OperationID)
					acceptedMu.Unlock()
					emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: "PROFILE_ADMISSION_CLOSED"})
				}
			case <-done:
				return
			}
		}
	}()

	emitter.emit(OnlineControlEvent{Type: "SESSION_READY"})
	type slotResponse struct {
		item        onlinePreparedRequest
		wire        []byte
		httpVersion string
		err         error
		diagnostic  *TransportDiagnostic
	}
	responses := make(chan slotResponse, plan.Rounds)
	var responseWG sync.WaitGroup
	launches := make([]SlotLaunch, 0, plan.Rounds)
	submitted := 0
	tolerance := time.Duration(plan.SchedulerToleranceMS) * time.Millisecond
	if tolerance <= 0 {
		tolerance = 2 * period
	}
	schedulerDone := make(chan struct{})
	go func() {
		defer close(schedulerDone)
		for index, state := range slots {
			if remaining := time.Until(state.cutoff); remaining > 0 {
				time.Sleep(remaining)
			}
			state.mu.Lock()
			item := state.noop
			if state.real != nil {
				item = *state.real
			}
			state.committed = true
			state.mu.Unlock()
			if item.real {
				emitter.emit(OnlineControlEvent{Type: "ACTION_ADMITTED", OperationID: item.operationID, Round: index + 1})
				engine.record(PrivateEvent{OperationID: item.operationID, Stage: "ONLINE_ACTION_ADMITTED", Round: index + 1})
			}
			if remaining := time.Until(state.deadline); remaining > 0 {
				time.Sleep(remaining)
			}
			if plan.FaultSchedulerStallSlot == index+1 && plan.FaultSchedulerStallMS > 0 {
				time.Sleep(time.Duration(plan.FaultSchedulerStallMS) * time.Millisecond)
			}
			submitTime := time.Now()
			slip := submitTime.Sub(state.deadline)
			launch := SlotLaunch{Session: 1, Slot: uint32(index + 1), DeadlineNS: state.deadline.Sub(processClock).Nanoseconds(), LaunchSlipNS: slip.Nanoseconds()}
			launch.ToleranceExceeded = slip > tolerance
			if slip >= period {
				launch.ScheduleMiss = true
				launches = append(launches, launch)
				continue
			}
			launch.SubmitNS = submitTime.Sub(processClock).Nanoseconds()
			launches = append(launches, launch)
			submitted++
			responseWG.Add(1)
			go func(value onlinePreparedRequest) {
				defer responseWG.Done()
				request, requestErr := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(value.wire))
				if requestErr != nil {
					responses <- slotResponse{item: value, err: requestErr}
					return
				}
				request.Header.Set("Content-Type", v8.OHTTPRequestContentType)
				request.Header.Set("X-AgentTool-Public-Session", "1")
				request.Header.Set("X-AgentTool-Public-Slot", strconv.FormatUint(uint64(value.slot.Slot), 10))
				request.ContentLength = int64(len(value.wire))
				response, requestErr := clientHTTP.Do(request)
				if requestErr != nil {
					responses <- slotResponse{item: value, err: requestErr}
					return
				}
				responseWire, readErr := io.ReadAll(io.LimitReader(response.Body, int64(plan.ResponseFinalBytes+1)))
				response.Body.Close()
				if readErr != nil || response.StatusCode != http.StatusOK || len(responseWire) != plan.ResponseFinalBytes {
					failureClass := "RESPONSE_BODY_LENGTH_MISMATCH"
					if readErr != nil {
						failureClass = "RESPONSE_READ_ERROR"
					} else if response.StatusCode != http.StatusOK {
						failureClass = "GATEWAY_NON_200"
					}
					diagnostic := &TransportDiagnostic{Slot: value.slot.Slot, HTTPStatus: response.StatusCode,
						ObservedBodyBytes: len(responseWire), ExpectedBodyBytes: plan.ResponseFinalBytes,
						FailureClass: failureClass}
					if readErr != nil {
						diagnostic.Error = readErr.Error()
					}
					responses <- slotResponse{item: value,
						err: fmt.Errorf("online canonical response validation failed: slot=%d http_status=%d observed_body_bytes=%d expected_body_bytes=%d class=%s",
							value.slot.Slot, response.StatusCode, len(responseWire), plan.ResponseFinalBytes, failureClass),
						diagnostic: diagnostic}
					return
				}
				responses <- slotResponse{item: value, wire: responseWire, httpVersion: response.Proto}
			}(item)
		}
		responseWG.Wait()
		close(responses)
	}()

	results := make([]ClientResult, 0, plan.MaximumRealOperations)
	transportFailure := false
	transportDiagnostics := make([]TransportDiagnostic, 0)
	for response := range responses {
		if response.err != nil || response.httpVersion != "HTTP/2.0" {
			transportFailure = true
			if response.diagnostic != nil {
				transportDiagnostics = append(transportDiagnostics, *response.diagnostic)
			} else if response.err != nil {
				transportDiagnostics = append(transportDiagnostics, TransportDiagnostic{Slot: response.item.slot.Slot,
					FailureClass: "TRANSPORT_ERROR", Error: response.err.Error()})
			}
			continue
		}
		opened, err := engine.client.DecapsulateResponse(response.item.context, response.wire)
		if err != nil {
			transportFailure = true
			continue
		}
		decoded, innerSlot, err := engine.codec.DecodeKnownLengthResponseBound(opened)
		if err != nil || innerSlot != response.item.slot {
			transportFailure = true
			continue
		}
		if decoded.Status != v9ohttp.StatusWait {
			result := ClientResult{OperationID: decoded.OperationID, Status: decoded.Status,
				Payload: decoded.Payload, Round: int(response.item.slot.Slot)}
			results = append(results, result)
			engine.record(PrivateEvent{OperationID: decoded.OperationID, Stage: "CLIENT_BHTTP_DECODED",
				Status: fmt.Sprintf("%d", decoded.Status), Round: int(response.item.slot.Slot)})
			emitter.emit(OnlineControlEvent{Type: "RESULT_AVAILABLE", OperationID: decoded.OperationID, Round: int(response.item.slot.Slot), Result: &result})
		}
	}
	<-schedulerDone
	engine.workers.Wait()
	close(done)
	sort.Slice(results, func(i, j int) bool { return results[i].Round < results[j].Round })
	delivered := make(map[string]bool, len(results))
	for _, result := range results {
		delivered[result.OperationID] = true
	}
	acceptedMu.Lock()
	acceptedCopy := append([]string(nil), acceptedIDs...)
	notAdmittedCopy := append([]string(nil), resolvedNotAdmitted...)
	acceptedMu.Unlock()
	pending := make([]string, 0)
	for _, operationID := range acceptedCopy {
		if !delivered[operationID] {
			pending = append(pending, operationID)
		}
	}
	scheduleMisses := 0
	for _, launch := range launches {
		if launch.ScheduleMiss {
			scheduleMisses++
		}
	}
	status := "COMPLETE"
	if scheduleMisses > 0 {
		status = "SESSION_SCHEDULE_FAILURE"
	} else if transportFailure || submitted != plan.Rounds {
		status = "SESSION_TRANSPORT_FAILURE"
	} else if len(pending) > 0 {
		status = "SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT"
	}
	result := RunResult{ProfileID: plan.ProfileID, Rounds: plan.Rounds, Admitted: len(acceptedCopy),
		ProviderInvocations: engine.providerCalls.Load(), DummyProviderOperations: 0,
		Results: results, PrivateEvents: append([]PrivateEvent(nil), engine.events...),
		PublicRelayEvents: relay.Events(), AfterCutoffOperations: []string{"atomic slot snapshot", "PreparedSlot.Send", "one fixed-size writer.Write", "byte-count validation"},
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes,
		SessionStatus: status, PublicSetupEvents: setupEvents, SlotLaunches: launches,
		ScheduleMisses: scheduleMisses, PendingOperationIDs: pending, SilentCommittedLosses: 0,
		ClientRelayHTTPVersion: preconnectProto, RelayGatewayHTTPVersion: "HTTP/2.0",
		OnlineMode: true, StartupActionCount: 0, AcceptedOperationIDs: acceptedCopy,
		ResolvedNotAdmittedIDs: notAdmittedCopy, FrameworkWaiterIDs: append([]string(nil), pending...),
		TransportDiagnostics: transportDiagnostics, ProviderDiagnostics: engine.providerDiagnostics()}
	if status == "COMPLETE" {
		emitter.emit(OnlineControlEvent{Type: "SESSION_COMPLETE"})
	} else {
		emitter.emit(OnlineControlEvent{Type: "SESSION_FAILURE", Reason: status})
	}
	return result, nil
}
