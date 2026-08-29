package v7

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
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
}

func OpenEffectRecoveryJournal(path string) (*EffectRecoveryJournal, error) {
	journal := &EffectRecoveryJournal{path: path, entries: make(map[string]recoveryEntry)}
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return journal, nil
		}
		return nil, err
	}
	if err := json.Unmarshal(raw, &journal.entries); err != nil {
		return nil, fmt.Errorf("V7 recovery journal integrity/format error: %w", err)
	}
	return journal, nil
}

func (j *EffectRecoveryJournal) persistLocked() error {
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
	j.entries[operationID] = recoveryEntry{OperationID: operationID, Semantics: semantics, Stage: RecoveryAccepted}
	return j.persistLocked()
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
	return j.persistLocked()
}

func (j *EffectRecoveryJournal) Commit(operationID string, result gatewayv2.ResultRecord) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[operationID]
	if !ok || (entry.Stage != RecoveryProviderStarted && entry.Stage != RecoveryAccepted) {
		return errors.New("result commit without pending operation")
	}
	entry.Stage = RecoveryResultCommitted
	entry.Status = result.Status
	entry.Payload = base64.StdEncoding.EncodeToString(result.Payload[:result.PayloadLen])
	j.entries[operationID] = entry
	return j.persistLocked()
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
	return j.persistLocked()
}

func (j *EffectRecoveryJournal) Recover(operationID string) (RecoveryDecision, gatewayv2.ResultRecord, error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	entry, ok := j.entries[operationID]
	if !ok {
		return "", gatewayv2.ResultRecord{}, errors.New("unknown operation")
	}
	switch entry.Stage {
	case RecoveryAccepted:
		return RecoveryExecute, gatewayv2.ResultRecord{}, nil
	case RecoveryProviderStarted:
		if entry.Semantics == gatewayv2.NonIdempotentEffect {
			return RecoveryOutcomeUnknown, gatewayv2.ResultRecord{Status: gatewayv2.StatusAmbiguous,
				OperationID: gatewayv2.OperationID(operationID)}, nil
		}
		return RecoveryExecute, gatewayv2.ResultRecord{}, nil
	case RecoveryResultCommitted, RecoveryResultDelivered:
		raw, err := base64.StdEncoding.DecodeString(entry.Payload)
		if err != nil || len(raw) > gatewayv2.ResultPayloadBytes {
			return "", gatewayv2.ResultRecord{}, errors.New("invalid committed result")
		}
		result := gatewayv2.ResultRecord{Status: entry.Status, OperationID: gatewayv2.OperationID(operationID),
			PayloadLen: uint16(len(raw))}
		copy(result.Payload[:], raw)
		return RecoveryReturnResult, result, nil
	default:
		return "", gatewayv2.ResultRecord{}, errors.New("unknown recovery stage")
	}
}
