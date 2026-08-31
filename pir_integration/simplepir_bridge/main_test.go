package main

import (
	"bytes"
	"encoding/json"
	"testing"
)

func TestApplicationResponseSendBoundaryIsContentIndependent(t *testing.T) {
	responses := []interactiveResponse{
		{Type: "PIR_RESULT", OperationID: "real", Record: "AA==", Correct: true},
		{Type: "PIR_RESULT", OperationID: "noop", Record: "VV==", Correct: true},
		{Type: "PIR_RESULT", OperationID: "wait", Record: "//==", Correct: true},
	}
	for _, response := range responses {
		var output bytes.Buffer
		sendNS, err := emitInteractiveResponse(json.NewEncoder(&output), response)
		if err != nil || sendNS <= 0 || output.Len() == 0 {
			t.Fatalf("application response boundary failed for %s: send=%d bytes=%d err=%v",
				response.OperationID, sendNS, output.Len(), err)
		}
	}
}
