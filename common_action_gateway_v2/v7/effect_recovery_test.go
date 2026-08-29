package v7

import (
	"path/filepath"
	"testing"

	gatewayv2 "common-action-gateway-v2"
)

func reopenRecovery(t *testing.T, path string) *EffectRecoveryJournal {
	t.Helper()
	journal, err := OpenEffectRecoveryJournal(path)
	if err != nil {
		t.Fatal(err)
	}
	return journal
}

func TestCrashAfterAcceptedBeforeProviderIsRetryableForAllSemantics(t *testing.T) {
	for _, semantics := range []gatewayv2.EffectSemantics{gatewayv2.ReadOnly, gatewayv2.IdempotentEffect, gatewayv2.NonIdempotentEffect} {
		path := filepath.Join(t.TempDir(), string(semantics)+".json")
		journal := reopenRecovery(t, path)
		if err := journal.Accept("op", semantics); err != nil {
			t.Fatal(err)
		}
		decision, _, err := reopenRecovery(t, path).Recover("op")
		if err != nil || decision != RecoveryExecute {
			t.Fatalf("semantics=%s decision=%s err=%v", semantics, decision, err)
		}
	}
}

func TestCrashAfterProviderStartUsesDeclaredEffectSemantics(t *testing.T) {
	for _, test := range []struct {
		semantics gatewayv2.EffectSemantics
		want      RecoveryDecision
	}{
		{gatewayv2.ReadOnly, RecoveryExecute},
		{gatewayv2.IdempotentEffect, RecoveryExecute},
		{gatewayv2.NonIdempotentEffect, RecoveryOutcomeUnknown},
	} {
		path := filepath.Join(t.TempDir(), string(test.semantics)+".json")
		journal := reopenRecovery(t, path)
		_ = journal.Accept("op", test.semantics)
		_ = journal.MarkProviderStarted("op")
		decision, result, err := reopenRecovery(t, path).Recover("op")
		if err != nil || decision != test.want {
			t.Fatalf("semantics=%s decision=%s err=%v", test.semantics, decision, err)
		}
		if test.want == RecoveryOutcomeUnknown && result.Status != gatewayv2.StatusAmbiguous {
			t.Fatal("ambiguous effect did not fail closed")
		}
	}
}

func TestCommittedResultRecoveryDoesNotReplayEffect(t *testing.T) {
	path := filepath.Join(t.TempDir(), "journal.json")
	journal := reopenRecovery(t, path)
	_ = journal.Accept("op", gatewayv2.NonIdempotentEffect)
	_ = journal.MarkProviderStarted("op")
	committed := result("op", 0)
	copy(committed.Payload[:], []byte("committed"))
	committed.PayloadLen = uint16(len("committed"))
	if err := journal.Commit("op", committed); err != nil {
		t.Fatal(err)
	}
	decision, recovered, err := reopenRecovery(t, path).Recover("op")
	if err != nil || decision != RecoveryReturnResult || string(recovered.Payload[:recovered.PayloadLen]) != "committed" {
		t.Fatalf("decision=%s payload=%q err=%v", decision, recovered.Payload[:recovered.PayloadLen], err)
	}
}

func TestCrashAfterFrameworkDeliveryRemainsDeduplicated(t *testing.T) {
	path := filepath.Join(t.TempDir(), "journal.json")
	journal := reopenRecovery(t, path)
	_ = journal.Accept("op", gatewayv2.IdempotentEffect)
	_ = journal.MarkProviderStarted("op")
	_ = journal.Commit("op", result("op", 0))
	_ = journal.MarkResultDelivered("op")
	decision, _, err := reopenRecovery(t, path).Recover("op")
	if err != nil || decision != RecoveryReturnResult {
		t.Fatalf("decision=%s err=%v", decision, err)
	}
}
