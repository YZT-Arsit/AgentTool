package canonicalv9

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	gatewayv2 "common-action-gateway-v2"
	"common-action-gateway-v2/v7"
	"common-action-gateway-v2/v8"
)

type RecoveryMatrixRow struct {
	Semantics  string `json:"semantics"`
	CrashPoint string `json:"crash_point"`
	Expected   string `json:"expected"`
	Observed   string `json:"observed"`
	Status     string `json:"status"`
	Pass       bool   `json:"pass"`
}

func recoveryExpected(semantics gatewayv2.EffectSemantics, started bool) v7.RecoveryDecision {
	if started && semantics == gatewayv2.NonIdempotentEffect {
		return v7.RecoveryOutcomeUnknown
	}
	return v7.RecoveryExecute
}

func recoveryOperation(ordinal int) string { return fmt.Sprintf("recovery-%03d", ordinal) }

// RecoveryMatrix exercises the exact journal, ready queue, in-memory
// publication, and PreparedSlot types used by Run. It restarts those durable
// objects from disk at every credited crash point.
func RecoveryMatrix(root string, capacity int) ([]RecoveryMatrixRow, error) {
	if _, err := os.Stat(root); err == nil {
		return nil, errors.New("refusing to overwrite recovery matrix state")
	} else if !errors.Is(err, os.ErrNotExist) {
		return nil, err
	}
	if err := os.MkdirAll(root, 0o700); err != nil {
		return nil, err
	}
	semantics := []gatewayv2.EffectSemantics{gatewayv2.ReadOnly, gatewayv2.IdempotentEffect, gatewayv2.NonIdempotentEffect}
	type earlyPoint struct {
		name    string
		started bool
	}
	early := []earlyPoint{
		{"BEFORE_PROVIDER_START", false},
		{"AFTER_DURABLE_PROVIDER_START_BEFORE_CALL", true},
		{"AFTER_PROVIDER_CALL_BEGINS", true},
		{"AFTER_PROVIDER_RESULT_BEFORE_DURABLE_COMMIT", true},
	}
	rows := make([]RecoveryMatrixRow, 0, len(semantics)*7)
	ordinal := 0
	for _, semantic := range semantics {
		for _, point := range early {
			ordinal++
			directory := filepath.Join(root, fmt.Sprintf("%03d-%s-%s", ordinal, semantic, point.name))
			journalPath := filepath.Join(directory, "effect_recovery.json")
			journal, err := v7.OpenEffectRecoveryJournal(journalPath)
			if err != nil {
				return nil, err
			}
			operationID := recoveryOperation(ordinal)
			if err := journal.Accept(operationID, semantic); err != nil {
				return nil, err
			}
			if point.started {
				if err := journal.MarkProviderStarted(operationID); err != nil {
					return nil, err
				}
			}
			restarted, err := v7.OpenEffectRecoveryJournal(journalPath)
			if err != nil {
				return nil, err
			}
			observed, _, err := restarted.Recover(operationID)
			if err != nil {
				return nil, err
			}
			expected := recoveryExpected(semantic, point.started)
			rows = append(rows, RecoveryMatrixRow{string(semantic), point.name, string(expected), string(observed), "RECOVERED", observed == expected})
		}

		for _, point := range []string{"AFTER_DURABLE_RESULT_COMMIT_BEFORE_PUBLICATION", "AFTER_PUBLICATION_BEFORE_PUBLIC_RESPONSE", "AFTER_PUBLIC_RESPONSE_SEND_BEFORE_GATEWAY_ACK"} {
			ordinal++
			directory := filepath.Join(root, fmt.Sprintf("%03d-%s-%s", ordinal, semantic, point))
			journalPath := filepath.Join(directory, "effect_recovery.json")
			readyPath := filepath.Join(directory, "ready_results.json")
			operationID := recoveryOperation(ordinal)
			journal, err := v7.OpenEffectRecoveryJournal(journalPath)
			if err != nil {
				return nil, err
			}
			if err := journal.Accept(operationID, semantic); err != nil {
				return nil, err
			}
			if err := journal.MarkProviderStarted(operationID); err != nil {
				return nil, err
			}
			result := resultRecord(operationID, gatewayv2.StatusOK, []byte("committed-local-result"))
			if err := journal.Commit(operationID, result); err != nil {
				return nil, err
			}
			ready, err := v7.OpenDurableReadyQueue(readyPath, capacity)
			if err != nil {
				return nil, err
			}
			if point != "AFTER_DURABLE_RESULT_COMMIT_BEFORE_PUBLICATION" {
				if _, err := ready.Enqueue(result, time.Now().UnixNano()); err != nil {
					return nil, err
				}
			}
			if point == "AFTER_PUBLICATION_BEFORE_PUBLIC_RESPONSE" {
				memory, _ := v8.NewMemoryDeliveryQueue(capacity)
				if err := memory.PublishDurable(result); err != nil || memory.SnapshotEligible(1) == nil {
					return nil, errors.New("recovery matrix memory publication failed")
				}
			}
			if point == "AFTER_PUBLIC_RESPONSE_SEND_BEFORE_GATEWAY_ACK" {
				reserved, err := ready.ReserveEligible(1, 1)
				if err != nil || reserved == nil {
					return nil, errors.New("recovery matrix could not reserve durable result")
				}
				ack := make(chan string, 1)
				prepared := v8.PreparedSlot{Frame: bytes.Repeat([]byte{0x55}, 800), OperationID: operationID, Ack: ack}
				var wire bytes.Buffer
				if err := prepared.Send(&wire); err != nil || len(wire.Bytes()) != 800 {
					return nil, errors.New("recovery matrix PreparedSlot send failed")
				}
				// Simulate the crash by intentionally not applying the in-memory ack
				// to the durable Gateway delivery state.
			}
			restartedJournal, err := v7.OpenEffectRecoveryJournal(journalPath)
			if err != nil {
				return nil, err
			}
			decision, recovered, err := restartedJournal.Recover(operationID)
			if err != nil {
				return nil, err
			}
			observed := string(decision)
			pass := decision == v7.RecoveryReturnResult && gatewayv2.OperationIDString(recovered.OperationID) == operationID
			if point != "AFTER_DURABLE_RESULT_COMMIT_BEFORE_PUBLICATION" {
				restartedReady, err := v7.OpenDurableReadyQueue(readyPath, capacity)
				if err != nil {
					return nil, err
				}
				pass = pass && restartedReady.Pending() == 1
				observed += "+READY_REPLAYABLE"
			}
			rows = append(rows, RecoveryMatrixRow{string(semantic), point, "RETURN_COMMITTED_RESULT", observed, "RECOVERED", pass})
		}
	}
	return rows, nil
}
