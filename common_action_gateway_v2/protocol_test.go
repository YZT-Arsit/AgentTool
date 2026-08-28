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
	if err := EncodeRequest(aead, frame, nonce, 99, op); err != nil {
		t.Fatal(err)
	}
	if len(frame) != 1024 {
		t.Fatalf("frame grew to %d", len(frame))
	}
	decoded, err := DecodeRequest(aead, frame, 99)
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
	if err := builder.Prepare(waitFrame, nonceA, 99, 1, 1, nil); err != nil {
		t.Fatal(err)
	}
	record := ResultRecord{Session: 1, RequestSlot: 1, Status: StatusOK, OperationID: OperationID("real")}
	if err := builder.Prepare(resultFrame, nonceB, 99, 1, 2, &record); err != nil {
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
		if err := builder.Prepare(frame, nonce, 99, 1, 1, &record); err != nil {
			panic(err)
		}
	})
	if allocations != 0 {
		t.Fatalf("critical preparation allocated %.2f objects/call", allocations)
	}
}

func TestPublicHeaderIsAuthenticated(t *testing.T) {
	aead, _ := ParseKey("00112233445566778899aabbccddeeff")
	frame := make([]byte, 1024)
	nonce := make([]byte, nonceBytes)
	_, _ = rand.Read(nonce)
	op := PrivateOperation{Session: 1, Slot: 2, Action: ActionTool, OperationID: OperationID("aad")}
	if err := EncodeRequest(aead, frame, nonce, 77, op); err != nil {
		t.Fatal(err)
	}
	for _, offset := range []int{0, 2, 4, 8, 12} {
		changed := append([]byte(nil), frame...)
		changed[offset] ^= 1
		if _, err := DecodeRequest(aead, changed, 77); err == nil {
			t.Fatalf("header mutation at %d was accepted", offset)
		}
	}
}

func TestSequenceValidatorRejectsReplayAndWrongSession(t *testing.T) {
	v := NewSequenceValidator(7, DirectionRequest, 2, 2)
	first := PublicFrameHeader{Version: ProtocolVersion, Direction: DirectionRequest, ProfileID: 7, Session: 0, Slot: 1}
	if err := v.Accept(first); err != nil {
		t.Fatal(err)
	}
	if err := v.Accept(first); err == nil {
		t.Fatal("duplicate frame accepted")
	}
	v = NewSequenceValidator(7, DirectionRequest, 2, 2)
	wrong := first
	wrong.Session = 1
	if err := v.Accept(wrong); err == nil {
		t.Fatal("non-monotonic session accepted")
	}
}
