package v7

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"sync"

	gatewayv2 "common-action-gateway-v2"
)

type RecoveryStage string

const (
	RecoveryAccepted        RecoveryStage = "REQUEST_ACCEPTED"
	RecoveryProviderStarted RecoveryStage = "PROVIDER_STARTED"
	RecoveryResultCommitted RecoveryStage = "RESULT_COMMITTED"
	RecoveryResultDelivered RecoveryStage = "RESULT_DELIVERED"
)

type RecoveryDecision string

const (
	RecoveryExecute        RecoveryDecision = "EXECUTE"
	RecoveryReturnResult   RecoveryDecision = "RETURN_COMMITTED_RESULT"
	RecoveryOutcomeUnknown RecoveryDecision = "EFFECT_OUTCOME_UNKNOWN"
)

type recoveryEntry struct {
	OperationID string                    `json:"operation_id"`
	Semantics   gatewayv2.EffectSemantics `json:"semantics"`
	Stage       RecoveryStage             `json:"stage"`
	Status      byte                      `json:"status,omitempty"`
	Payload     string                    `json:"payload_base64,omitempty"`
}

type EffectRecoveryJournal struct {
	mu      sync.Mutex
	path    string
	entries map[string]recoveryEntry
	wal     bool
}

type recoveryLogRecord struct {
	Schema string        `json:"schema"`
	Entry  recoveryEntry `json:"entry"`
}

const recoveryWALSchema = "gateway-v7-effect-recovery-wal-v1"

func OpenEffectRecoveryJournal(path string) (*EffectRecoveryJournal, error) {
	journal := &EffectRecoveryJournal{path: path, entries: make(map[string]recoveryEntry), wal: true}
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return journal, nil
		}
		return nil, err
	}
	if err := json.Unmarshal(raw, &journal.entries); err == nil {
		journal.wal = false // Legacy snapshot; migrate atomically on first mutation.
		return journal, nil
	}
	journal.entries = make(map[string]recoveryEntry)
	for lineNumber, line := range bytes.Split(raw, []byte{'\n'}) {
		if len(bytes.TrimSpace(line)) == 0 {
			continue
		}
		var record recoveryLogRecord
		if err := json.Unmarshal(line, &record); err != nil || record.Schema != recoveryWALSchema || record.Entry.OperationID == "" {
			return nil, fmt.Errorf("V7 recovery journal integrity/format error at WAL line %d", lineNumber+1)
		}
		journal.entries[record.Entry.OperationID] = record.Entry
	}
	return journal, nil
}

func (j *EffectRecoveryJournal) ensureWALLocked() error {
	if j.wal {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(j.path), 0o700); err != nil {
		return err
	}
	temporary := j.path + ".next"
	file, err := os.OpenFile(temporary, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	operationIDs := make([]string, 0, len(j.entries))
	for operationID := range j.entries {
		operationIDs = append(operationIDs, operationID)
	}
	sort.Strings(operationIDs)
	encoder := json.NewEncoder(file)
	for _, operationID := range operationIDs {
		if err = encoder.Encode(recoveryLogRecord{Schema: recoveryWALSchema, Entry: j.entries[operationID]}); err != nil {
			break
		}
	}
	if err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if err := os.Rename(temporary, j.path); err != nil {
		return err
	}
	j.wal = true
	return nil
}

func (j *EffectRecoveryJournal) persistEntryLocked(entry recoveryEntry) error {
	if err := j.ensureWALLocked(); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(j.path), 0o700); err != nil {
		return err
	}
	file, err := os.OpenFile(j.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	err = json.NewEncoder(file).Encode(recoveryLogRecord{Schema: recoveryWALSchema, Entry: entry})
	if err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err != nil {
		return err
	}
	return closeErr
}

func (j *EffectRecoveryJournal) Accept(operationID string, semantics gatewayv2.EffectSemantics) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	if operationID == "" {
		return errors.New("empty operation ID")
	}
	if entry, ok := j.entries[operationID]; ok {
		if entry.Semantics != semantics {
			return errors.New("operation ID reused with different semantics")
		}
		return nil
	}
	entry := recoveryEntry{OperationID: operationID, Semantics: semantics, Stage: RecoveryAccepted}
	j.entries[operationID] = entry
	if err := j.persistEntryLocked(entry); err != nil {
		delete(j.entries, operationID)
		return err
	}
	return nil
}

func (j *EffectRecoveryJournal) MarkProviderStarted(operationID string) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[operationID]
	if !ok || entry.Stage != RecoveryAccepted {
		return errors.New("provider start without accepted operation")
	}
	entry.Stage = RecoveryProviderStarted
	j.entries[operationID] = entry
	if err := j.persistEntryLocked(entry); err != nil {
		entry.Stage = RecoveryAccepted
		j.entries[operationID] = entry
		return err
	}
	return nil
}

// Begin durably creates a fresh operation directly in PROVIDER_STARTED, avoiding
// a second whole-file persistence step on the normal path. Existing entries use
// the same recovery decisions as Accept followed by Recover/MarkProviderStarted.
func (j *EffectRecoveryJournal) Begin(operationID string, semantics gatewayv2.EffectSemantics) (RecoveryDecision, gatewayv2.ResultRecord, error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	if operationID == "" {
		return "", gatewayv2.ResultRecord{}, errors.New("empty operation ID")
	}
	entry, ok := j.entries[operationID]
	if !ok {
		entry = recoveryEntry{OperationID: operationID, Semantics: semantics, Stage: RecoveryProviderStarted}
		j.entries[operationID] = entry
		if err := j.persistEntryLocked(entry); err != nil {
			delete(j.entries, operationID)
			return "", gatewayv2.ResultRecord{}, err
		}
		return RecoveryExecute, gatewayv2.ResultRecord{}, nil
	}
	if entry.Semantics != semantics {
		return "", gatewayv2.ResultRecord{}, errors.New("operation ID reused with different semantics")
	}
	if entry.Stage == RecoveryAccepted {
		previous := entry
		entry.Stage = RecoveryProviderStarted
		j.entries[operationID] = entry
		if err := j.persistEntryLocked(entry); err != nil {
			j.entries[operationID] = previous
			return "", gatewayv2.ResultRecord{}, err
		}
		return RecoveryExecute, gatewayv2.ResultRecord{}, nil
	}
	return recoverEntry(entry)
}

func (j *EffectRecoveryJournal) Commit(operationID string, result gatewayv2.ResultRecord) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[operationID]
	if !ok || (entry.Stage != RecoveryProviderStarted && entry.Stage != RecoveryAccepted) {
		return errors.New("result commit without pending operation")
	}
	previous := entry
	entry.Stage = RecoveryResultCommitted
	entry.Status = result.Status
	entry.Payload = base64.StdEncoding.EncodeToString(result.Payload[:result.PayloadLen])
	j.entries[operationID] = entry
	if err := j.persistEntryLocked(entry); err != nil {
		j.entries[operationID] = previous
		return err
	}
	return nil
}

func (j *EffectRecoveryJournal) MarkResultDelivered(operationID string) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[operationID]
	if !ok || (entry.Stage != RecoveryResultCommitted && entry.Stage != RecoveryResultDelivered) {
		return errors.New("delivery without committed result")
	}
	entry.Stage = RecoveryResultDelivered
	j.entries[operationID] = entry
	if err := j.persistEntryLocked(entry); err != nil {
		entry.Stage = RecoveryResultCommitted
		j.entries[operationID] = entry
		return err
	}
	return nil
}

func (j *EffectRecoveryJournal) Recover(operationID string) (RecoveryDecision, gatewayv2.ResultRecord, error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[operationID]
	if !ok {
		return "", gatewayv2.ResultRecord{}, errors.New("unknown operation")
	}
	return recoverEntry(entry)
}

func recoverEntry(entry recoveryEntry) (RecoveryDecision, gatewayv2.ResultRecord, error) {
	switch entry.Stage {
	case RecoveryAccepted:
		return RecoveryExecute, gatewayv2.ResultRecord{}, nil
	case RecoveryProviderStarted:
		if entry.Semantics == gatewayv2.NonIdempotentEffect {
			return RecoveryOutcomeUnknown, gatewayv2.ResultRecord{Status: gatewayv2.StatusAmbiguous,
				OperationID: gatewayv2.OperationID(entry.OperationID)}, nil
		}
		return RecoveryExecute, gatewayv2.ResultRecord{}, nil
	case RecoveryResultCommitted, RecoveryResultDelivered:
		raw, err := base64.StdEncoding.DecodeString(entry.Payload)
		if err != nil || len(raw) > gatewayv2.ResultPayloadBytes {
			return "", gatewayv2.ResultRecord{}, errors.New("invalid committed result")
		}
		result := gatewayv2.ResultRecord{Status: entry.Status, OperationID: gatewayv2.OperationID(entry.OperationID),
			PayloadLen: uint16(len(raw))}
		copy(result.Payload[:], raw)
		return RecoveryReturnResult, result, nil
	default:
		return "", gatewayv2.ResultRecord{}, errors.New("unknown recovery stage")
	}
}
