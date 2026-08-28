package gatewayv2

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
)

type EffectSemantics string

const (
	ReadOnly            EffectSemantics = "READ_ONLY"
	IdempotentEffect    EffectSemantics = "IDEMPOTENT_EFFECT"
	NonIdempotentEffect EffectSemantics = "NON_IDEMPOTENT_EFFECT"
)

func (value EffectSemantics) valid() bool {
	return value == ReadOnly || value == IdempotentEffect || value == NonIdempotentEffect
}

type JournalState string

const (
	JournalPrepared  JournalState = "PREPARED"
	JournalCommitted JournalState = "COMMITTED"
	JournalRetryable JournalState = "RETRYABLE"
	JournalAmbiguous JournalState = "AMBIGUOUS_RECONCILIATION_REQUIRED"
)

type JournalDecision string

const (
	JournalExecute         JournalDecision = "EXECUTE"
	JournalReturnCommitted JournalDecision = "RETURN_COMMITTED"
	JournalFailAmbiguous   JournalDecision = "FAIL_AMBIGUOUS"
)

type JournalEntry struct {
	OperationID string          `json:"operation_id"`
	Semantics   EffectSemantics `json:"semantics"`
	State       JournalState    `json:"state"`
	Status      byte            `json:"status,omitempty"`
	Payload     string          `json:"payload_base64,omitempty"`
}

type OperationJournal struct {
	mu      sync.Mutex
	path    string
	entries map[string]JournalEntry
}

func OpenOperationJournal(path string) (*OperationJournal, error) {
	journal := &OperationJournal{path: path, entries: make(map[string]JournalEntry)}
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return journal, nil
		}
		return nil, err
	}
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &journal.entries); err != nil {
			return nil, fmt.Errorf("operation journal integrity/format error: %w", err)
		}
	}
	return journal, nil
}

func (j *OperationJournal) persistLocked() error {
	if err := os.MkdirAll(filepath.Dir(j.path), 0o700); err != nil {
		return err
	}
	temporary := j.path + ".next"
	raw, err := json.Marshal(j.entries)
	if err != nil {
		return err
	}
	file, err := os.OpenFile(temporary, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	if _, err = file.Write(raw); err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Rename(temporary, j.path)
}

func (j *OperationJournal) Begin(operationID string, semantics EffectSemantics) (JournalDecision, ResultRecord, error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	if !semantics.valid() {
		return "", ResultRecord{}, fmt.Errorf("invalid effect semantics %q", semantics)
	}
	if entry, ok := j.entries[operationID]; ok {
		if entry.Semantics != semantics {
			return "", ResultRecord{}, errors.New("operation ID reused with different effect semantics")
		}
		if entry.State == JournalCommitted {
			result, err := entry.result()
			return JournalReturnCommitted, result, err
		}
		if semantics == NonIdempotentEffect {
			return JournalFailAmbiguous, ResultRecord{Status: StatusAmbiguous}, nil
		}
		return JournalExecute, ResultRecord{}, nil
	}
	j.entries[operationID] = JournalEntry{OperationID: operationID, Semantics: semantics, State: JournalPrepared}
	if err := j.persistLocked(); err != nil {
		delete(j.entries, operationID)
		return "", ResultRecord{}, err
	}
	return JournalExecute, ResultRecord{}, nil
}

func (j *OperationJournal) Complete(operationID string, result ResultRecord) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[operationID]
	if !ok {
		return errors.New("operation was not durably prepared")
	}
	entry.Status = result.Status
	entry.Payload = base64.StdEncoding.EncodeToString(result.Payload[:result.PayloadLen])
	if result.Status == StatusOK {
		entry.State = JournalCommitted
	} else if entry.Semantics == NonIdempotentEffect {
		entry.State = JournalAmbiguous
	} else {
		entry.State = JournalRetryable
	}
	j.entries[operationID] = entry
	return j.persistLocked()
}

func (entry JournalEntry) result() (ResultRecord, error) {
	raw, err := base64.StdEncoding.DecodeString(entry.Payload)
	if err != nil || len(raw) > ResultPayloadBytes {
		return ResultRecord{}, errors.New("invalid committed result in operation journal")
	}
	result := ResultRecord{Status: entry.Status, PayloadLen: uint16(len(raw))}
	copy(result.Payload[:], raw)
	result.OperationID = OperationID(entry.OperationID)
	return result, nil
}
