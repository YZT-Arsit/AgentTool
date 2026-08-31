package canonicalv9

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	gatewayv2 "common-action-gateway-v2"
	"common-action-gateway-v2/v7ohttp"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (function roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return function(request)
}

func providerDiagnosticEngine(client *http.Client) *engine {
	return &engine{
		plan:       Plan{ProviderCompletionBoundMS: 50},
		httpClient: client,
		started:    time.Now(),
	}
}

func TestProviderDiagnosticClassification(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		switch request.URL.Path {
		case "/ok":
			_, _ = writer.Write([]byte(`{"status":"OK","payload":"b2s="}`))
		case "/http":
			writer.WriteHeader(http.StatusServiceUnavailable)
			_, _ = writer.Write([]byte("unavailable"))
		case "/decode":
			_, _ = writer.Write([]byte("not-json"))
		case "/status":
			_, _ = writer.Write([]byte(`{"status":"ERROR","payload":""}`))
		default:
			http.NotFound(writer, request)
		}
	}))
	defer server.Close()

	transportError := errors.New("synthetic transport error")
	cases := []struct {
		name     string
		endpoint string
		client   *http.Client
		want     string
	}{
		{"ok", server.URL + "/ok", server.Client(), ProviderOK},
		{"transport", "http://127.0.0.1/execute", &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
			return nil, transportError
		})}, ProviderTransportError},
		{"deadline", "http://127.0.0.1/execute", &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
			return nil, context.DeadlineExceeded
		})}, ProviderContextDeadlineExceeded},
		{"http-non-2xx", server.URL + "/http", server.Client(), ProviderHTTPNon2XX},
		{"decode", server.URL + "/decode", server.Client(), ProviderResponseDecodeError},
		{"provider-status", server.URL + "/status", server.Client(), ProviderStatusError},
	}
	for _, item := range cases {
		t.Run(item.name, func(t *testing.T) {
			attempt := providerDiagnosticEngine(item.client).callProvider(
				RouteSpec{RouteHandle: "private-route", Endpoint: item.endpoint}, "operation", nil,
			)
			if attempt.diagnostic.Class != item.want {
				t.Fatalf("provider diagnostic class=%s want=%s diagnostic=%+v", attempt.diagnostic.Class, item.want, attempt.diagnostic)
			}
			if (item.want == ProviderOK) != (attempt.status == gatewayv2.StatusOK) {
				t.Fatalf("public result semantics changed for %s: status=%d", item.want, attempt.status)
			}
		})
	}
}

func runOnlineControl(t *testing.T, plan Plan, actions []ActionSpec) (RunResult, []OnlineControlEvent) {
	t.Helper()
	controlReader, controlWriter := io.Pipe()
	eventReader, eventWriter := io.Pipe()
	resultChannel := make(chan RunResult, 1)
	errorChannel := make(chan error, 1)
	go func() {
		result, err := RunOnline(plan, controlReader, eventWriter)
		_ = eventWriter.Close()
		resultChannel <- result
		errorChannel <- err
	}()
	decoder := json.NewDecoder(bufio.NewReader(eventReader))
	encoder := json.NewEncoder(controlWriter)
	events := make([]OnlineControlEvent, 0)
	seenResults := 0
	for {
		var event OnlineControlEvent
		if err := decoder.Decode(&event); err != nil {
			break
		}
		events = append(events, event)
		if event.Type == "SESSION_READY" && len(actions) > 0 {
			if err := encoder.Encode(OnlineControlMessage{Type: "SUBMIT_RESOLVED_ACTION", Action: &actions[0]}); err != nil {
				t.Fatal(err)
			}
		}
		if event.Type == "RESULT_AVAILABLE" {
			seenResults++
			if seenResults < len(actions) {
				if err := encoder.Encode(OnlineControlMessage{Type: "SUBMIT_RESOLVED_ACTION", Action: &actions[seenResults]}); err != nil {
					t.Fatal(err)
				}
			}
		}
	}
	_ = controlWriter.Close()
	result := <-resultChannel
	if err := <-errorChannel; err != nil {
		t.Fatal(err)
	}
	return result, events
}

func liveSchedulerPlan(t *testing.T, rounds int, providerDelay time.Duration) (Plan, *int) {
	t.Helper()
	providerCalls := new(int)
	provider := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		(*providerCalls)++
		if providerDelay > 0 {
			time.Sleep(providerDelay)
		}
		body := []byte(`{"status":"OK","payload":"c2NoZWR1bGVk"}`)
		writer.Header().Set("Content-Type", "application/json")
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write(body)
	}))
	t.Cleanup(provider.Close)
	plan := diagnosticPlan()
	plan.ProfileID = "V11_1-SCHEDULER-DEVELOPMENT"
	plan.StateDirectory = filepath.Join(t.TempDir(), "state")
	plan.Rounds = rounds
	plan.AdmissionRounds = 1
	plan.RoundPeriodMS = 5
	plan.SchedulerToleranceMS = 3
	plan.Routes = []RouteSpec{{RouteHandle: "private-route", ActionKind: "REAL_TOOL",
		EffectSemantics: "READ_ONLY", Endpoint: provider.URL, PolicyID: "private-policy"}}
	plan.Actions = []ActionSpec{{OperationID: "scheduled-operation", ActionKind: "REAL_TOOL",
		RouteHandle: "private-route", EffectSemantics: "READ_ONLY", PolicyID: "private-policy",
		ProtectedArguments: bytes.Repeat([]byte("a"), 16)}}
	return plan, providerCalls
}

func diagnosticPlan() Plan {
	return Plan{ProfileID: "V9-CANONICAL-TEST", StateDirectory: "unused", Rounds: 13,
		AdmissionRounds: 1, MaximumRealOperations: 1, RoundPeriodMS: 5,
		ProviderCompletionBoundMS: 50, RequestBHTTPBytes: 1024, ResponseBHTTPBytes: 768,
		RequestFinalBytes: 1079, ResponseFinalBytes: 800}
}

func TestCanonicalWireSizesAndAdmissionBinding(t *testing.T) {
	result, err := Diagnostics(diagnosticPlan())
	if err != nil {
		t.Fatal(err)
	}
	if !result.AllWireSizesPass || len(result.SizeMatrix) != 10 {
		t.Fatalf("canonical size matrix failed: %+v", result.SizeMatrix)
	}
	if !result.AllAdmissionChecksPass || len(result.AdmissionBinding) != 7 {
		t.Fatalf("canonical admission matrix failed: %+v", result.AdmissionBinding)
	}
}

func TestCanonicalLiveRecoveryTypesAtEveryGatewayCrashPoint(t *testing.T) {
	rows, err := RecoveryMatrix(filepath.Join(t.TempDir(), "matrix"), 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 21 {
		t.Fatalf("got %d Gateway recovery rows, want 21", len(rows))
	}
	for _, row := range rows {
		if !row.Pass {
			t.Fatalf("recovery mismatch: %+v", row)
		}
	}
}

func TestCanonicalPlanRejectsNonLoopbackPrivateProvider(t *testing.T) {
	plan := diagnosticPlan()
	plan.Routes = []RouteSpec{{RouteHandle: "private-route", ActionKind: "REAL_TOOL",
		EffectSemantics: "READ_ONLY", Endpoint: "http://example.invalid", PolicyID: "private-policy"}}
	plan.Actions = []ActionSpec{{OperationID: "operation", ActionKind: "REAL_TOOL",
		RouteHandle: "private-route", EffectSemantics: "READ_ONLY", PolicyID: "private-policy"}}
	if err := validatePlan(plan); err == nil {
		t.Fatal("canonical development plan accepted a non-loopback provider")
	}
}

func TestCanonicalAcceptUsesLiveRecoveryDecisionOnRestart(t *testing.T) {
	providerCalls := 0
	provider := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		providerCalls++
		body := []byte(`{"status":"OK","payload":"cmVjb3ZlcmVk"}`)
		writer.Header().Set("Content-Type", "application/json")
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write(body)
	}))
	defer provider.Close()

	for _, item := range []struct {
		name           string
		semantics      gatewayv2.EffectSemantics
		expectedCalls  int
		expectedStatus byte
	}{
		{"read-only-retry", gatewayv2.ReadOnly, 1, gatewayv2.StatusOK},
		{"idempotent-retry", gatewayv2.IdempotentEffect, 1, gatewayv2.StatusOK},
		{"non-idempotent-unknown", gatewayv2.NonIdempotentEffect, 0, gatewayv2.StatusAmbiguous},
	} {
		t.Run(item.name, func(t *testing.T) {
			providerCalls = 0
			plan := diagnosticPlan()
			plan.StateDirectory = filepath.Join(t.TempDir(), "state")
			plan.Routes = []RouteSpec{{RouteHandle: "private-route", ActionKind: "REAL_TOOL",
				EffectSemantics: string(item.semantics), Endpoint: provider.URL, PolicyID: "private-policy"}}
			engine, err := newEngine(plan)
			if err != nil {
				t.Fatal(err)
			}
			operationID := "restart-operation"
			if err := engine.journal.Accept(operationID, item.semantics); err != nil {
				t.Fatal(err)
			}
			if err := engine.journal.MarkProviderStarted(operationID); err != nil {
				t.Fatal(err)
			}
			authorization, _ := json.Marshal(map[string]string{"effect_semantics": string(item.semantics), "policy_id": "private-policy"})
			action := v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionRealTool,
				RouteHandle: []byte("private-route"), OperationID: []byte(operationID), Authorization: authorization}
			if err := engine.accept(action, 2); err != nil {
				t.Fatal(err)
			}
			engine.workers.Wait()
			deadline := time.Now().Add(time.Second)
			for engine.ready.Pending() == 0 && time.Now().Before(deadline) {
				time.Sleep(time.Millisecond)
			}
			if providerCalls != item.expectedCalls || engine.ready.Pending() != 1 {
				t.Fatalf("provider calls=%d pending=%d", providerCalls, engine.ready.Pending())
			}
			selected, err := engine.ready.ReserveEligible(1, 2)
			if err != nil || selected == nil || selected.Status != item.expectedStatus {
				t.Fatalf("recovered result mismatch: result=%+v err=%v", selected, err)
			}
		})
	}
}

func TestV11_1HTTP2SlotsAreIndependentAndPreconnected(t *testing.T) {
	plan, providerCalls := liveSchedulerPlan(t, 20, 2*time.Millisecond)
	plan.FaultDelayResponseSlot = 1
	plan.FaultDelayResponseMS = 50
	result, err := Run(plan)
	if err != nil {
		t.Fatal(err)
	}
	if result.SessionStatus != "COMPLETE" || result.ScheduleMisses != 0 || len(result.PublicRelayEvents) != plan.Rounds {
		t.Fatalf("independent scheduler failed: status=%s misses=%d events=%d", result.SessionStatus, result.ScheduleMisses, len(result.PublicRelayEvents))
	}
	if *providerCalls != 1 || len(result.Results) != 1 || result.Results[0].OperationID != "scheduled-operation" {
		t.Fatalf("functional result mismatch: calls=%d results=%+v", *providerCalls, result.Results)
	}
	if result.ClientRelayHTTPVersion != "HTTP/2.0" || result.RelayGatewayHTTPVersion != "HTTP/2.0" {
		t.Fatalf("canonical mode did not negotiate HTTP/2: %+v", result)
	}
	for _, event := range result.PublicRelayEvents {
		if event.ClientHTTPVersion != "HTTP/2.0" || event.GatewayHTTPVersion != "HTTP/2.0" {
			t.Fatalf("slot %d was not multiplexed over HTTP/2: %+v", event.Round, event)
		}
	}
	if len(result.PublicSetupEvents) < 6 || result.PublicSetupEvents[len(result.PublicSetupEvents)-1].Stage != "T0_ASSIGNED" {
		t.Fatalf("public setup/T0 evidence incomplete: %+v", result.PublicSetupEvents)
	}
	// The 50 ms response delay is ten public periods. Later requests must still
	// be submitted near their independent deadlines.
	if result.SlotLaunches[9].ScheduleMiss || result.SlotLaunches[9].LaunchSlipNS > int64(3*time.Millisecond) {
		t.Fatalf("delayed stream blocked later slot: %+v", result.SlotLaunches[9])
	}
}

func TestV11_1SchedulerStallFailsWithoutCatchUpBurst(t *testing.T) {
	plan, _ := liveSchedulerPlan(t, 13, 0)
	plan.SchedulerToleranceMS = 1
	plan.FaultSchedulerStallSlot = 3
	plan.FaultSchedulerStallMS = 25
	result, err := Run(plan)
	if err != nil {
		t.Fatal(err)
	}
	if result.SessionStatus != "SESSION_SCHEDULE_FAILURE" || result.ScheduleMisses == 0 {
		t.Fatalf("scheduler stall did not fail closed: status=%s misses=%d", result.SessionStatus, result.ScheduleMisses)
	}
	if len(result.PublicRelayEvents) >= plan.Rounds {
		t.Fatal("missed slots were silently emitted as a catch-up burst")
	}
	for _, launch := range result.SlotLaunches {
		if launch.ScheduleMiss && launch.SubmitNS == 0 {
			continue
		}
		if launch.ScheduleMiss {
			t.Fatalf("missed slot unexpectedly submitted: %+v", launch)
		}
	}
}

func TestV11_1ExpiredSlotCannotBeSubmittedUnderLooseTolerance(t *testing.T) {
	plan, _ := liveSchedulerPlan(t, 13, 0)
	plan.SchedulerToleranceMS = 100
	plan.FaultSchedulerStallSlot = 2
	plan.FaultSchedulerStallMS = plan.RoundPeriodMS + 2
	result, err := Run(plan)
	if err != nil {
		t.Fatal(err)
	}
	if result.SessionStatus != "SESSION_SCHEDULE_FAILURE" || result.ScheduleMisses == 0 {
		t.Fatalf("expired slot was not failed closed: status=%s misses=%d", result.SessionStatus, result.ScheduleMisses)
	}
	for _, launch := range result.SlotLaunches {
		if launch.ScheduleMiss && launch.SubmitNS != 0 {
			t.Fatalf("expired slot %d was transmitted as catch-up", launch.Slot)
		}
	}
}

func TestV12_1SubperiodSlipIsDiagnosticNotScheduleMiss(t *testing.T) {
	plan, _ := liveSchedulerPlan(t, 13, 0)
	plan.RoundPeriodMS = 20
	plan.SchedulerToleranceMS = 1
	plan.FaultSchedulerStallSlot = 3
	plan.FaultSchedulerStallMS = 5
	result, err := Run(plan)
	if err != nil {
		t.Fatal(err)
	}
	if result.SessionStatus != "COMPLETE" || result.ScheduleMisses != 0 || len(result.PublicRelayEvents) != plan.Rounds {
		t.Fatalf("subperiod diagnostic slip changed public schedule: status=%s misses=%d events=%d", result.SessionStatus, result.ScheduleMisses, len(result.PublicRelayEvents))
	}
	if !result.SlotLaunches[2].ToleranceExceeded || result.SlotLaunches[2].ScheduleMiss {
		t.Fatalf("subperiod slip was not separated from a true miss: %+v", result.SlotLaunches[2])
	}
}

func TestV11_1GatewaySlotRegistryRejectsInvalidAndDuplicateSlots(t *testing.T) {
	plan := diagnosticPlan()
	plan.StateDirectory = filepath.Join(t.TempDir(), "state")
	engine, err := newEngine(plan)
	if err != nil {
		t.Fatal(err)
	}
	request, _ := http.NewRequest(http.MethodPost, "https://local.invalid", nil)
	request.Header.Set("X-AgentTool-Public-Session", "1")
	for _, invalid := range []string{"0", "14"} {
		request.Header.Set("X-AgentTool-Public-Slot", invalid)
		if _, err := engine.claimPublicSlot(request); err == nil {
			t.Fatalf("accepted invalid slot %s", invalid)
		}
	}
	request.Header.Set("X-AgentTool-Public-Slot", "2")
	if _, err := engine.claimPublicSlot(request); err != nil {
		t.Fatal(err)
	}
	if _, err := engine.claimPublicSlot(request); err == nil {
		t.Fatal("duplicate public slot accepted")
	}
}

func TestV11_2OnlineCausalActionsUseOnePreconnectedSession(t *testing.T) {
	plan, providerCalls := liveSchedulerPlan(t, 25, time.Millisecond)
	plan.Actions = nil
	plan.AdmissionRounds = 12
	plan.MaximumRealOperations = 2
	plan.PreparationLeadMS = 2
	actions := []ActionSpec{
		{OperationID: "online-op-1", ActionKind: "REAL_TOOL", RouteHandle: "private-route", EffectSemantics: "READ_ONLY", PolicyID: "private-policy", ProtectedArguments: []byte("first")},
		{OperationID: "online-op-2", ActionKind: "REAL_TOOL", RouteHandle: "private-route", EffectSemantics: "READ_ONLY", PolicyID: "private-policy", ProtectedArguments: []byte("second")},
	}
	result, events := runOnlineControl(t, plan, actions)
	if result.SessionStatus != "COMPLETE" || !result.OnlineMode || result.StartupActionCount != 0 {
		t.Fatalf("online session failed: %+v", result)
	}
	if result.Admitted != 2 || len(result.Results) != 2 || *providerCalls != 2 {
		t.Fatalf("online functional mismatch: admitted=%d results=%d calls=%d", result.Admitted, len(result.Results), *providerCalls)
	}
	if len(result.PublicRelayEvents) != plan.Rounds || result.ClientRelayHTTPVersion != "HTTP/2.0" || result.RelayGatewayHTTPVersion != "HTTP/2.0" {
		t.Fatal("online trajectory did not preserve one fixed HTTP/2 public session")
	}
	resultOne, acceptTwo := -1, -1
	for index, event := range events {
		if event.Type == "RESULT_AVAILABLE" && event.OperationID == "online-op-1" {
			resultOne = index
		}
		if event.Type == "ACTION_ACCEPTED" && event.OperationID == "online-op-2" {
			acceptTwo = index
		}
	}
	if resultOne < 0 || acceptTwo <= resultOne {
		t.Fatalf("second action was not causally submitted after first result: %+v", events)
	}
}

func TestV11_2OnlineModeRejectsStartupActionList(t *testing.T) {
	plan, _ := liveSchedulerPlan(t, 13, 0)
	plan.PreparationLeadMS = 2
	if _, err := RunOnline(plan, bytes.NewReader(nil), io.Discard); err == nil {
		t.Fatal("online mode accepted a future action list at T0")
	}
}

func TestV11_2OnlineSchedulerFailureIsExplicitAndDoesNotRestart(t *testing.T) {
	plan, _ := liveSchedulerPlan(t, 13, 0)
	plan.Actions = nil
	plan.PreparationLeadMS = 2
	plan.SchedulerToleranceMS = 1
	plan.FaultSchedulerStallSlot = 3
	plan.FaultSchedulerStallMS = 25
	result, events := runOnlineControl(t, plan, nil)
	if result.SessionStatus != "SESSION_SCHEDULE_FAILURE" || result.ScheduleMisses == 0 {
		t.Fatalf("online schedule failure was not explicit: %+v", result)
	}
	failures, ready := 0, 0
	for _, event := range events {
		if event.Type == "SESSION_FAILURE" {
			failures++
		}
		if event.Type == "SESSION_READY" {
			ready++
		}
	}
	if failures != 1 || ready != 1 {
		t.Fatalf("online failure started or reported multiple sessions: ready=%d failures=%d", ready, failures)
	}
	for _, launch := range result.SlotLaunches {
		if launch.ScheduleMiss && launch.SubmitNS != 0 {
			t.Fatalf("failed online slot was transmitted as catch-up: %+v", launch)
		}
	}
}

func TestV12_1OnlineSubperiodSlipIsDiagnosticNotScheduleMiss(t *testing.T) {
	plan, _ := liveSchedulerPlan(t, 13, 0)
	plan.Actions = nil
	plan.PreparationLeadMS = 2
	plan.RoundPeriodMS = 20
	plan.SchedulerToleranceMS = 1
	plan.FaultSchedulerStallSlot = 3
	plan.FaultSchedulerStallMS = 5
	result, _ := runOnlineControl(t, plan, nil)
	if result.SessionStatus != "COMPLETE" || result.ScheduleMisses != 0 || len(result.PublicRelayEvents) != plan.Rounds {
		t.Fatalf("online subperiod slip changed public schedule: %+v", result)
	}
	if !result.SlotLaunches[2].ToleranceExceeded || result.SlotLaunches[2].ScheduleMiss {
		t.Fatalf("online subperiod slip was not diagnostic-only: %+v", result.SlotLaunches[2])
	}
}

func TestV12TimingProfileEmitsEverySlotAfterThirtyFiveMillisecondDelay(t *testing.T) {
	plan, _ := liveSchedulerPlan(t, 8, 0)
	plan.Actions = nil
	plan.ProfileID = "V12-TIMING-INDIST-H50-H3000-P10-PIR60"
	plan.ProfileClass = TimingIndistinguishabilityProfile
	plan.PublicSessionLivenessCapMS = TimingPublicSessionLivenessCapMS
	plan.PreparationLeadMS = 2
	plan.RoundPeriodMS = 10
	plan.SchedulerToleranceMS = 1
	plan.FaultSchedulerStallSlot = 3
	plan.FaultSchedulerStallMS = 35
	result, _ := runOnlineControl(t, plan, nil)
	if result.SessionStatus != "COMPLETE" || !result.PublicTranscriptComplete {
		t.Fatalf("jitter-tolerant transcript failed: %+v", result)
	}
	if result.EmittedCells != plan.Rounds || len(result.PublicRelayEvents) != plan.Rounds || len(result.SlotLaunches) != plan.Rounds {
		t.Fatalf("late slot changed fixed transcript: emitted=%d relay=%d launches=%d", result.EmittedCells, len(result.PublicRelayEvents), len(result.SlotLaunches))
	}
	if result.NominalLateCells == 0 || result.InfrastructureLivenessFailure {
		t.Fatalf("artificial lateness was not retained as diagnostics: %+v", result)
	}
	for index, launch := range result.SlotLaunches {
		if !launch.Emitted || launch.Slot != uint32(index+1) {
			t.Fatalf("authenticated slot missing or reordered: %+v", result.SlotLaunches)
		}
		if index > 0 && launch.DispatchNS-result.SlotLaunches[index-1].DispatchNS < int64(10*time.Millisecond) {
			t.Fatalf("public recovery produced catch-up burst: %+v", result.SlotLaunches)
		}
	}
}

func TestV11_2OnlineCapacityRejectsWithoutSecondSession(t *testing.T) {
	plan, providerCalls := liveSchedulerPlan(t, 13, time.Millisecond)
	plan.Actions = nil
	plan.PreparationLeadMS = 2
	actions := []ActionSpec{
		{OperationID: "capacity-op-1", ActionKind: "REAL_TOOL", RouteHandle: "private-route", EffectSemantics: "READ_ONLY", PolicyID: "private-policy"},
		{OperationID: "capacity-op-2", ActionKind: "REAL_TOOL", RouteHandle: "private-route", EffectSemantics: "READ_ONLY", PolicyID: "private-policy"},
	}
	result, events := runOnlineControl(t, plan, actions)
	if result.SessionStatus != "COMPLETE" || result.Admitted != 1 || len(result.Results) != 1 || *providerCalls != 1 {
		t.Fatalf("capacity rejection damaged admitted work: %+v calls=%d", result, *providerCalls)
	}
	rejected := 0
	ready := 0
	for _, event := range events {
		if event.Type == "ACTION_REJECTED" && event.OperationID == "capacity-op-2" && event.Reason == "PROFILE_CAPACITY_EXCEEDED" {
			rejected++
		}
		if event.Type == "SESSION_READY" {
			ready++
		}
	}
	if rejected != 1 || ready != 1 {
		t.Fatalf("capacity outcome/session count mismatch: rejected=%d ready=%d", rejected, ready)
	}
}
