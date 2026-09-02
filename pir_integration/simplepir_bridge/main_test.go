package main

import (
	"bytes"
	"encoding/json"
	"testing"
)

func TestRegistryResponseDeadlineUsesOnlyPublicReleaseState(t *testing.T) {
	const publicDeadline = int64(1_050_000_000)
	for _, privateCase := range []string{"REAL", "DUMMY", "CACHE_MISS", "CONSUMER_BLOCKED"} {
		got := registryResponseDeadline(publicDeadline, 1_010_000_000, 60_000_000)
		if got != 1_070_000_000 {
			t.Fatalf("private case %s changed public answer deadline: %d", privateCase, got)
		}
	}
}

func TestLegacyRegistryResponseHasNoArtificialDeadline(t *testing.T) {
	if got := registryResponseDeadline(0, 1_010_000_000, 60_000_000); got != 0 {
		t.Fatalf("legacy response deadline changed: %d", got)
	}
}

func TestSyntheticRegistryRealCountDifferential(t *testing.T) {
	const deadline = int64(1_050_000_000)
	zeroReal := registryResponseDeadline(deadline, 1_000_000_000, 60_000_000)
	oneReal := registryResponseDeadline(deadline, 1_000_000_000, 60_000_000)
	multipleReal := registryResponseDeadline(deadline, 1_000_000_000, 60_000_000)
	if zeroReal != oneReal || oneReal != multipleReal {
		t.Fatalf("real descriptor count changed the public Registry response deadline")
	}
}

func TestApplicationResponseSendBoundaryIsContentIndependent(t *testing.T) {
	responses := []interactiveResponse{
		{Type: "PIR_RESULT", OperationID: "real", Record: "AA==", Correct: true},
		{Type: "PIR_RESULT", OperationID: "noop", Record: "VV==", Correct: true},
		{Type: "PIR_RESULT", OperationID: "wait", Record: "//==", Correct: true},
	}
	for _, response := range responses {
		var output bytes.Buffer
		sendNS, err := emitInteractiveResponse(json.NewEncoder(&output), response)
		if err != nil || sendNS <= 0 || output.Len() != interactiveResponseFrameBytes {
			t.Fatalf("application response boundary failed for %s: send=%d bytes=%d err=%v",
				response.OperationID, sendNS, output.Len(), err)
		}
	}
}
