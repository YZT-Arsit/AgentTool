package gatewayv2

import (
	"path/filepath"
	"testing"
)

func committedResult(id string, payload string) ResultRecord {
	result := ResultRecord{Status: StatusOK, OperationID: OperationID(id), PayloadLen: uint16(len(payload))}
	copy(result.Payload[:], []byte(payload))
	return result
}

func TestJournalCrashBeforeCommitRespectsProviderSemantics(t *testing.T) {
	path := filepath.Join(t.TempDir(), "operations.json")
	journal, err := OpenOperationJournal(path)
	if err != nil {
		t.Fatal(err)
	}
	decision, _, err := journal.Begin("non-idempotent", NonIdempotentEffect)
	if err != nil || decision != JournalExecute {
		t.Fatalf("begin=%s err=%v", decision, err)
	}

	// Simulate process death after durable PREPARED and before a provider result
	// can be committed. Reopening must not re-execute an irreversible provider.
	restarted, err := OpenOperationJournal(path)
	if err != nil {
		t.Fatal(err)
	}
	decision, result, err := restarted.Begin("non-idempotent", NonIdempotentEffect)
	if err != nil || decision != JournalFailAmbiguous || result.Status != StatusAmbiguous {
		t.Fatalf("decision=%s status=%d err=%v", decision, result.Status, err)
	}
}

func TestJournalIdempotentEffectCanRetrySameOperationIDAfterCrash(t *testing.T) {
	path := filepath.Join(t.TempDir(), "operations.json")
	journal, _ := OpenOperationJournal(path)
	decision, _, _ := journal.Begin("idempotent", IdempotentEffect)
	if decision != JournalExecute {
		t.Fatal(decision)
	}
	restarted, _ := OpenOperationJournal(path)
	decision, _, err := restarted.Begin("idempotent", IdempotentEffect)
	if err != nil || decision != JournalExecute {
		t.Fatalf("decision=%s err=%v", decision, err)
	}
}

func TestJournalCrashAfterCommitReturnsDurableResultWithoutEffectReplay(t *testing.T) {
	path := filepath.Join(t.TempDir(), "operations.json")
	journal, _ := OpenOperationJournal(path)
	_, _, _ = journal.Begin("committed", NonIdempotentEffect)
	if err := journal.Complete("committed", committedResult("committed", "once")); err != nil {
		t.Fatal(err)
	}
	restarted, _ := OpenOperationJournal(path)
	decision, result, err := restarted.Begin("committed", NonIdempotentEffect)
	if err != nil || decision != JournalReturnCommitted || string(result.Payload[:result.PayloadLen]) != "once" {
		t.Fatalf("decision=%s payload=%q err=%v", decision, result.Payload[:result.PayloadLen], err)
	}
}

func TestJournalFailedNonIdempotentCallRequiresReconciliation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "operations.json")
	journal, _ := OpenOperationJournal(path)
	_, _, _ = journal.Begin("ambiguous", NonIdempotentEffect)
	failed := ResultRecord{Status: StatusTimeout, OperationID: OperationID("ambiguous")}
	if err := journal.Complete("ambiguous", failed); err != nil {
		t.Fatal(err)
	}
	restarted, _ := OpenOperationJournal(path)
	decision, _, _ := restarted.Begin("ambiguous", NonIdempotentEffect)
	if decision != JournalFailAmbiguous {
		t.Fatal(decision)
	}
}

func TestJournalRejectsOperationIDSemanticReuse(t *testing.T) {
	journal, _ := OpenOperationJournal(filepath.Join(t.TempDir(), "operations.json"))
	_, _, _ = journal.Begin("same", ReadOnly)
	if _, _, err := journal.Begin("same", IdempotentEffect); err == nil {
		t.Fatal("semantic mismatch accepted")
	}
}
