package gatewayv2

import "testing"

func TestEffectGateAllowsOneEffectPerPrivateOperationID(t *testing.T) {
	gate := NewEffectGate()
	id := OperationID("effect-1")
	if !gate.Reserve(id) {
		t.Fatal("first effect reservation rejected")
	}
	if gate.Reserve(id) {
		t.Fatal("duplicate effect reservation accepted")
	}
	if !gate.Reserve(OperationID("effect-2")) {
		t.Fatal("independent effect reservation rejected")
	}
}
