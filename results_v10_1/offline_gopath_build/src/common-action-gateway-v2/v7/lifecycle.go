package v7

import (
	"encoding/csv"
	"fmt"
	"os"
	"sort"
	"strconv"
	"sync"
)

type LifecycleStage string

const (
	StageAdmitted           LifecycleStage = "ADMITTED"
	StageRequestSent        LifecycleStage = "REQUEST_SENT"
	StageRequestReceived    LifecycleStage = "REQUEST_RECEIVED"
	StageWorkerDecrypted    LifecycleStage = "WORKER_DECRYPTED"
	StageProviderStarted    LifecycleStage = "PROVIDER_STARTED"
	StageEffectExecuted     LifecycleStage = "EFFECT_EXECUTED"
	StageResultJournaled    LifecycleStage = "RESULT_JOURNALED"
	StageResultPublished    LifecycleStage = "RESULT_READY_PUBLISHED"
	StagePacerObserved      LifecycleStage = "PACER_OBSERVED"
	StageResultCellSent     LifecycleStage = "RESULT_CELL_SENT"
	StageClientReceived     LifecycleStage = "CLIENT_RECEIVED"
	StageFrameworkDelivered LifecycleStage = "FRAMEWORK_DELIVERED"
)

type LifecycleEvent struct {
	OperationID string
	Stage       LifecycleStage
	MonotonicNS int64
	Session     uint32
	Slot        uint32
	Detail      string
}

// LifecycleRecorder is private diagnostic state. It does not write, signal, or
// perform callbacks on the public release path; DumpCSV is called after a run.
type LifecycleRecorder struct {
	mu     sync.Mutex
	events []LifecycleEvent
}

func (r *LifecycleRecorder) Record(event LifecycleEvent) {
	r.mu.Lock()
	r.events = append(r.events, event)
	r.mu.Unlock()
}

func (r *LifecycleRecorder) Events() []LifecycleEvent {
	r.mu.Lock()
	defer r.mu.Unlock()
	result := append([]LifecycleEvent(nil), r.events...)
	sort.SliceStable(result, func(i, j int) bool { return result[i].MonotonicNS < result[j].MonotonicNS })
	return result
}

func (r *LifecycleRecorder) DumpCSV(path string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	writer := csv.NewWriter(file)
	if err := writer.Write([]string{"operation_id", "stage", "monotonic_ns", "session", "slot", "detail"}); err != nil {
		return err
	}
	for _, event := range r.Events() {
		if err := writer.Write([]string{event.OperationID, string(event.Stage), strconv.FormatInt(event.MonotonicNS, 10),
			strconv.FormatUint(uint64(event.Session), 10), strconv.FormatUint(uint64(event.Slot), 10), event.Detail}); err != nil {
			return fmt.Errorf("write lifecycle: %w", err)
		}
	}
	writer.Flush()
	return writer.Error()
}
