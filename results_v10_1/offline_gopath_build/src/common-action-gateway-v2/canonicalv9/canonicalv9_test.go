package canonicalv9

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	gatewayv2 "common-action-gateway-v2"
	"common-action-gateway-v2/v7ohttp"
)

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
