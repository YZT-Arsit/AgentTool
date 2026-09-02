package canonicalv9

import (
	"testing"
	"time"
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
			eligible, arrival, previous, 10*time.Millisecond, 50*time.Millisecond,
		)
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
	)
	if want := origin.Add(90 * time.Millisecond); !got.Equal(want) {
		t.Fatalf("got %s want %s", got, want)
	}
}

func TestSyntheticT7ResponseDifferential(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	ordinaryTool := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 50*time.Millisecond)
	agentAsTool := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 50*time.Millisecond)
	if !ordinaryTool.Equal(agentAsTool) {
		t.Fatalf("T7 private action kind changed public response deadline")
	}
}

func TestSyntheticT9ResponseDifferential(t *testing.T) {
	origin := time.Unix(0, 1_000_000_000)
	earlyReady := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 50*time.Millisecond)
	lateReadyWithinCutoff := gatewayResponseDeadline(origin, origin, time.Time{}, 10*time.Millisecond, 50*time.Millisecond)
	if !earlyReady.Equal(lateReadyWithinCutoff) {
		t.Fatalf("T9 provider readiness changed public response deadline")
	}
}
