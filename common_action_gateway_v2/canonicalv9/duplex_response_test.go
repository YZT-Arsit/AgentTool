package canonicalv9

import (
	"net/http/httptest"
	"testing"
	"time"

	"common-action-gateway-v2/v8"
)

func TestGatewayResponseDeadlineIgnoresPrivateResponseSemantics(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	eligible := origin.Add(20 * time.Millisecond)
	arrival := origin.Add(21 * time.Millisecond)
	previous := origin.Add(10 * time.Millisecond)
	want := origin.Add(71 * time.Millisecond)

	for _, privateCase := range []string{
		"NOOP", "REAL", "WAIT", "RESULT", "EARLY_PROVIDER", "LATE_PROVIDER",
		"ORDINARY_TOOL", "AGENT_AS_TOOL",
	} {
		got := gatewayResponseDeadline(
			eligible, arrival, previous, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond,
		)
		want = origin.Add(50 * time.Millisecond)
		if !got.Equal(want) {
			t.Fatalf("private case %s changed response deadline: got %s want %s", privateCase, got, want)
		}
	}
}

func TestGatewayResponseDeadlineUsesOnlyPublicRecurrence(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	got := gatewayResponseDeadline(
		origin.Add(40*time.Millisecond),
		origin.Add(35*time.Millisecond),
		origin.Add(50*time.Millisecond),
		10*time.Millisecond,
		50*time.Millisecond,
		50*time.Millisecond,
	)
	if want := origin.Add(90 * time.Millisecond); !got.Equal(want) {
		t.Fatalf("got %s want %s", got, want)
	}
}

func TestGatewayResponsePublicLagIsIdenticalForEverySlot(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	for _, slot := range []uint32{1, 2, 3, 506} {
		eligible := origin.Add(time.Duration(slot-1) * 10 * time.Millisecond)
		got := gatewayResponseDeadline(
			eligible, eligible.Add(time.Millisecond), time.Time{},
			10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond,
		)
		if want := eligible.Add(30 * time.Millisecond); !got.Equal(want) {
			t.Fatalf("slot %d release = %s, want %s", slot, got, want)
		}
	}
}

func TestSyntheticT7ResponseDifferential(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	ordinaryTool := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond)
	agentAsTool := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond)
	if !ordinaryTool.Equal(agentAsTool) {
		t.Fatalf("T7 private action kind changed public response deadline")
	}
}

func TestSyntheticT9ResponseDifferential(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	earlyReady := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond)
	lateReadyWithinCutoff := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond)
	if !earlyReady.Equal(lateReadyWithinCutoff) {
		t.Fatalf("T9 provider readiness changed public response deadline")
	}
}

func TestGatewayResponseLatePreparationWritesCommittedSlot(t *testing.T) {
	clock, err := newGatewayResponseVirtualizer(
		1, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond, 1, false, time.Now(),
	)
	if err != nil {
		t.Fatal(err)
	}
	eligible := time.Now().Add(5 * time.Millisecond)
	clock.setEligibility(1, eligible)
	writer := httptest.NewRecorder()
	err = clock.release(1, time.Now(), func(time.Time) (func() (v8.PreparedSlot, error), error) {
		return func() (v8.PreparedSlot, error) {
			time.Sleep(45 * time.Millisecond)
			return v8.PreparedSlot{Frame: []byte("fixed-frame")}, nil
		}, nil
	}, writer)
	if err != nil {
		t.Fatalf("late committed frame was dropped: %v", err)
	}
	releases := clock.wait()
	if len(releases) != 1 || !releases[0].DeadlineMiss ||
		!releases[0].ReleaseAttempted || !releases[0].WriteCompleted {
		t.Fatalf("late release accounting = %+v", releases)
	}
	if got := writer.Body.String(); got != "fixed-frame" {
		t.Fatalf("writer body = %q", got)
	}
}

func TestExactRelaySlotInventoryRejectsMissingOrDuplicate(t *testing.T) {
	complete := []v8.RelayPublicEvent{{Session: 1, Round: 1}, {Session: 1, Round: 2}}
	if !exactRelayPublicSlotInventory(complete, 2) {
		t.Fatal("complete inventory rejected")
	}
	if exactRelayPublicSlotInventory(complete[:1], 2) {
		t.Fatal("missing slot accepted")
	}
	duplicate := []v8.RelayPublicEvent{{Session: 1, Round: 1}, {Session: 1, Round: 1}}
	if exactRelayPublicSlotInventory(duplicate, 2) {
		t.Fatal("duplicate slot accepted")
	}
}

func v4r6SyntheticPublicPathPlan(t *testing.T, rounds int) Plan {
	plan, _ := liveSchedulerPlan(t, rounds, 0)
	plan.Actions = nil
	plan.ProfileID = "V12-TIMING-INDIST-V4R6-H50-H4500-P10-PIR60"
	plan.ProfileClass = TimingIndistinguishabilityProfile
	plan.TimingSemanticRevision = "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6"
	plan.AdmissionRounds = 450
	plan.AdmissionHorizonMS = 4500
	plan.MaximumRealOperations = 50
	plan.RoundPeriodMS = 10
	plan.PublicSessionLivenessCapMS = TimingPublicSessionLivenessCapMS
	plan.PIRResolutionPeriodMS = 60
	plan.PIRPublicEpochMS = 6000
	plan.PIRResolutionOpportunities = 100
	plan.PIRInitialLeadMS = 25
	plan.PreparationLeadMS = 1
	plan.ResponsePublicLagMS = 30
	plan.ResponsePreparationLeadMS = 20
	plan.ResponsePreparationWorkers = 6
	return plan
}

func assertCompleteV4R6SyntheticTranscript(t *testing.T, result RunResult, rounds int) {
	t.Helper()
	if result.SessionStatus != "COMPLETE" || !result.PublicTranscriptComplete {
		t.Fatalf("synthetic public transcript did not complete: %+v", result)
	}
	if result.EmittedCells != rounds || result.SuccessfulResponseWrites != rounds ||
		result.RelayApplicationReceivedCells != rounds || len(result.PublicRelayEvents) != rounds {
		t.Fatalf("response accounting mismatch: emitted=%d writes=%d relay=%d events=%d",
			result.EmittedCells, result.SuccessfulResponseWrites,
			result.RelayApplicationReceivedCells, len(result.PublicRelayEvents))
	}
	if !exactRelayPublicSlotInventory(result.PublicRelayEvents, rounds) {
		t.Fatalf("public Relay inventory is not exactly 1..%d", rounds)
	}
}

func TestV4R6SyntheticStartupStressPreservesEveryPublicSlot(t *testing.T) {
	cases := []struct {
		name             string
		schedulerStallMS int
		preparationMS    int
	}{
		{name: "cold_process_start"},
		{name: "delayed_gateway_arrival_within_public_bound", schedulerStallMS: 5},
		{name: "secret_independent_stall_before_slot_1", schedulerStallMS: 35},
		{name: "secret_independent_stall_immediately_before_F1", preparationMS: 45},
	}
	for _, item := range cases {
		t.Run(item.name, func(t *testing.T) {
			plan := v4r6SyntheticPublicPathPlan(t, 506)
			plan.FaultSchedulerStallSlot = 1
			plan.FaultSchedulerStallMS = item.schedulerStallMS
			plan.FaultDelayResponseSlot = 1
			plan.FaultDelayResponseMS = item.preparationMS
			result, _ := runOnlineControl(t, plan, nil)
			assertCompleteV4R6SyntheticTranscript(t, result, plan.Rounds)
			if item.preparationMS > plan.ResponsePreparationLeadMS &&
				!result.GatewayResponseReleases[0].DeadlineMiss {
				t.Fatal("injected pre-release stall was not retained as a deadline miss")
			}
		})
	}
}

func TestV4R6PrewarmedSecondSessionPreservesEveryPublicSlot(t *testing.T) {
	first, _ := runOnlineControl(t, v4r6SyntheticPublicPathPlan(t, 506), nil)
	assertCompleteV4R6SyntheticTranscript(t, first, 506)
	second, _ := runOnlineControl(t, v4r6SyntheticPublicPathPlan(t, 506), nil)
	assertCompleteV4R6SyntheticTranscript(t, second, 506)
}

func TestV4R7PublicCapacityBindsB200ToR521(t *testing.T) {
	plan := v4r6SyntheticPublicPathPlan(t, 521)
	plan.ProfileID = "V12-TIMING-INDIST-V4R7-H50-H4500-P10-B200-PIR60"
	plan.TimingSemanticRevision = "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R7"
	plan.ProviderCompletionBoundMS = 200
	if err := validatePlan(plan); err != nil {
		t.Fatalf("valid V4R7 plan rejected: %v", err)
	}
	for _, rounds := range []int{506, 520, 522} {
		mutated := plan
		mutated.Rounds = rounds
		if err := validatePlan(mutated); err == nil {
			t.Fatalf("V4R7 accepted R=%d instead of 521", rounds)
		}
	}
	diagnostics, err := Diagnostics(plan)
	if err != nil {
		t.Fatal(err)
	}
	if !diagnostics.AllWireSizesPass || !diagnostics.AllAdmissionChecksPass {
		t.Fatalf("V4R7 capacity/size diagnostics failed: %+v", diagnostics)
	}
}

func TestV4R7ProviderReadinessCannotMoveResponseDeadline(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	deadline := gatewayResponseDeadline(
		origin, origin, time.Time{}, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond,
	)
	for _, privateReadiness := range []time.Duration{0, 199 * time.Millisecond, 201 * time.Millisecond} {
		got := gatewayResponseDeadline(
			origin, origin, time.Time{}, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond,
		)
		if !got.Equal(deadline) {
			t.Fatalf("private readiness %s changed response deadline", privateReadiness)
		}
	}
}

func TestV4R8GatewayArrivalCannotMovePlannedResponseDeadline(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	eligible := origin.Add(100 * time.Millisecond)
	previous := origin.Add(110 * time.Millisecond)
	want := origin.Add(130 * time.Millisecond)
	for _, arrival := range []time.Time{
		origin.Add(80 * time.Millisecond),
		origin.Add(115 * time.Millisecond),
		origin.Add(500 * time.Millisecond),
	} {
		got := gatewayResponseDeadlineV4R8(
			eligible, previous, 10*time.Millisecond, 30*time.Millisecond,
		)
		if !got.Equal(want) {
			t.Fatalf("arrival %s moved V4R8 F_i: got %s want %s", arrival, got, want)
		}
	}
}

func TestV4R8PrivateResponseCasesCannotMovePlannedDeadline(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	eligible := origin.Add(20 * time.Millisecond)
	want := origin.Add(50 * time.Millisecond)
	for _, privateCase := range []string{
		"NOOP", "REAL", "WAIT", "RESULT", "PROVIDER_EARLY", "PROVIDER_LATE",
	} {
		got := gatewayResponseDeadlineV4R8(
			eligible, time.Time{}, 10*time.Millisecond, 30*time.Millisecond,
		)
		if !got.Equal(want) {
			t.Fatalf("private case %s moved V4R8 F_i: got %s want %s", privateCase, got, want)
		}
	}
}

func TestV4R8PlannedRecurrenceDoesNotPropagateArrivalPerturbation(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	previous := time.Time{}
	for slot := 0; slot < 12; slot++ {
		eligible := origin.Add(time.Duration(slot) * 10 * time.Millisecond)
		got := gatewayResponseDeadlineV4R8(
			eligible, previous, 10*time.Millisecond, 30*time.Millisecond,
		)
		want := eligible.Add(30 * time.Millisecond)
		if !got.Equal(want) {
			t.Fatalf("slot %d F_i = %s, want %s", slot+1, got, want)
		}
		previous = got
	}
}

func TestV4R8LateArrivalPreservesOriginalCutoffAndLateFrame(t *testing.T) {
	processClock := time.Now()
	clock, err := newGatewayResponseVirtualizer(
		1, 10*time.Millisecond, 30*time.Millisecond, 20*time.Millisecond, 1, true, processClock,
	)
	if err != nil {
		t.Fatal(err)
	}
	eligible := time.Now().Add(20 * time.Millisecond)
	plannedRelease := eligible.Add(30 * time.Millisecond)
	wantCutoff := eligible.Add(10 * time.Millisecond)
	clock.setEligibility(1, eligible)
	// The request is deliberately made physically available after F_1. The
	// recorded request-arrival timestamp is also after the original G_1.
	time.Sleep(time.Until(plannedRelease.Add(5 * time.Millisecond)))
	writer := httptest.NewRecorder()
	readyBetweenCutoffAndArrival := wantCutoff.Add(5 * time.Millisecond)
	var gotCutoff time.Time
	err = clock.release(1, plannedRelease.Add(2*time.Millisecond), func(cutoff time.Time) (func() (v8.PreparedSlot, error), error) {
		gotCutoff = cutoff
		frame := "WAIT"
		if !readyBetweenCutoffAndArrival.After(cutoff) {
			frame = "RESULT"
		}
		return func() (v8.PreparedSlot, error) {
			return v8.PreparedSlot{Frame: []byte(frame)}, nil
		}, nil
	}, writer)
	if err != nil {
		t.Fatal(err)
	}
	if !gotCutoff.Equal(wantCutoff) {
		t.Fatalf("late request redefined G_1: got %s want %s", gotCutoff, wantCutoff)
	}
	if got := writer.Body.String(); got != "WAIT" {
		t.Fatalf("post-cutoff result retroactively entered slot: %q", got)
	}
	releases := clock.wait()
	if len(releases) != 1 || !releases[0].DeadlineMiss || releases[0].ReleaseSlipNS <= 0 {
		t.Fatalf("late-frame accounting = %+v", releases)
	}
	wantReleaseNS := plannedRelease.Sub(processClock).Nanoseconds()
	if releases[0].ReleaseNS != wantReleaseNS {
		t.Fatalf("recorded planned F_1 = %d, want %d", releases[0].ReleaseNS, wantReleaseNS)
	}
}

func TestV4R8PublicProfilePreservesV4R7CapacityAndSizes(t *testing.T) {
	plan := v4r6SyntheticPublicPathPlan(t, 521)
	plan.ProfileID = "V12-TIMING-INDIST-V4R8-H50-H4500-P10-B200-PIR60"
	plan.TimingSemanticRevision = "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8"
	plan.ProviderCompletionBoundMS = 200
	if err := validatePlan(plan); err != nil {
		t.Fatalf("valid V4R8 plan rejected: %v", err)
	}
	if plan.Rounds != 521 || plan.PIRResolutionOpportunities != 100 ||
		plan.RequestFinalBytes != 1079 || plan.ResponseFinalBytes != 800 {
		t.Fatalf("V4R8 public shape changed: %+v", plan)
	}
	for _, rounds := range []int{520, 522} {
		mutated := plan
		mutated.Rounds = rounds
		if err := validatePlan(mutated); err == nil {
			t.Fatalf("V4R8 accepted R=%d", rounds)
		}
	}
}
