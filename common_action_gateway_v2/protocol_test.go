package gatewayv2

import (
	"crypto/rand"
	"testing"
)

func TestRequestFixedSizeRoundTrip(t *testing.T) {
	aead, err := ParseKey("00112233445566778899aabbccddeeff")
	if err != nil {
		t.Fatal(err)
	}
	frame := make([]byte, 1024)
	nonce := make([]byte, nonceBytes)
	_, _ = rand.Read(nonce)
	op := PrivateOperation{Session: 3, Slot: 7, Action: ActionTool, Provider: ProviderSlow,
		OperationID: OperationID("operation-7"), Payload: []byte("synthetic")}
	if err := EncodeRequest(aead, frame, nonce, op); err != nil {
		t.Fatal(err)
	}
	if len(frame) != 1024 {
		t.Fatalf("frame grew to %d", len(frame))
	}
	decoded, err := DecodeRequest(aead, frame)
	if err != nil {
		t.Fatal(err)
	}
	if decoded.Session != op.Session || decoded.Slot != op.Slot || decoded.Provider != op.Provider || OperationIDString(decoded.OperationID) != "operation-7" {
		t.Fatalf("round trip changed operation: %#v", decoded)
	}
}

func TestResultAndWaitUseSamePreparedSize(t *testing.T) {
	aead, err := ParseKey("00112233445566778899aabbccddeeff")
	if err != nil {
		t.Fatal(err)
	}
	builder := NewResponseFrameBuilder(aead, 1024)
	waitFrame := make([]byte, 1024)
	resultFrame := make([]byte, 1024)
	nonceA := make([]byte, nonceBytes)
	nonceB := make([]byte, nonceBytes)
	_, _ = rand.Read(nonceA)
	_, _ = rand.Read(nonceB)
	if err := builder.Prepare(waitFrame, nonceA, 1, 1, nil); err != nil {
		t.Fatal(err)
	}
	record := ResultRecord{Session: 1, RequestSlot: 1, Status: StatusOK, OperationID: OperationID("real")}
	if err := builder.Prepare(resultFrame, nonceB, 1, 2, &record); err != nil {
		t.Fatal(err)
	}
	if len(waitFrame) != len(resultFrame) || len(waitFrame) != 1024 {
		t.Fatal("RESULT and WAIT sizes differ")
	}
}

func TestResponsePreparationHasNoPerCallAllocation(t *testing.T) {
	aead, err := ParseKey("00112233445566778899aabbccddeeff")
	if err != nil {
		t.Fatal(err)
	}
	builder := NewResponseFrameBuilder(aead, 1024)
	frame := make([]byte, 1024)
	nonce := make([]byte, nonceBytes)
	record := ResultRecord{Status: StatusOK}
	allocations := testing.AllocsPerRun(1000, func() {
		if err := builder.Prepare(frame, nonce, 1, 1, &record); err != nil {
			panic(err)
		}
	})
	if allocations != 0 {
		t.Fatalf("critical preparation allocated %.2f objects/call", allocations)
	}
}
