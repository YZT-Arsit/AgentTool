package gatewayv2

import "testing"

func TestLateResultContinuesInNextPublicSession(t *testing.T) {
	if !resultEligibleForPublicSession(2, 3) {
		t.Fatal("a late private result must remain eligible for an already-scheduled later slot")
	}
	if resultEligibleForPublicSession(4, 3) {
		t.Fatal("a future-session result must remain privately queued")
	}
}
