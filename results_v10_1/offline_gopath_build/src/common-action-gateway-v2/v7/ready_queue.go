package v7

// This package is the V7 functional-closure layer.  It imports the frozen V6
// wire/result types, but does not modify the content-addressed V6 implementation.

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"sync"

	gatewayv2 "common-action-gateway-v2"
)

type DeliveryState string

const (
	DeliveryReady     DeliveryState = "READY"
	DeliveryInFlight  DeliveryState = "IN_FLIGHT"
	DeliveryDelivered DeliveryState = "DELIVERED"
)

type ReadyEntry struct {
	Sequence        uint64                 `json:"sequence"`
	Result          gatewayv2.ResultRecord `json:"result"`
	State           DeliveryState          `json:"state"`
	PublishedNS     int64                  `json:"published_ns"`
	PublicSession   uint32                 `json:"public_session,omitempty"`
	PublicSlot      uint32                 `json:"public_slot,omitempty"`
	DeliveryAttempt uint32                 `json:"delivery_attempt"`
}

type readySnapshot struct {
	Schema       string       `json:"schema"`
	Capacity     int          `json:"capacity"`
	NextSequence uint64       `json:"next_sequence"`
	Entries      []ReadyEntry `json:"entries"`
}

// DurableReadyQueue is a bounded private queue.  Publication and delivery-state
// transitions are committed by fsync + atomic rename.  An IN_FLIGHT entry is
// replayed after restart: duplicate delivery is safe because the trusted client
// deduplicates by operation_id, while silently losing a result is not safe.
type DurableReadyQueue struct {
	mu       sync.Mutex
	path     string
	capacity int
	next     uint64
	entries  []ReadyEntry
}

func OpenDurableReadyQueue(path string, capacity int) (*DurableReadyQueue, error) {
	if capacity < 1 {
		return nil, errors.New("ready queue capacity must be positive")
	}
	queue := &DurableReadyQueue{path: path, capacity: capacity}
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return queue, nil
		}
		return nil, err
	}
	var snapshot readySnapshot
	if err := json.Unmarshal(raw, &snapshot); err != nil {
		return nil, fmt.Errorf("ready queue integrity/format error: %w", err)
	}
	if snapshot.Schema != "gateway-v7-ready-queue-v1" || snapshot.Capacity != capacity {
		return nil, errors.New("ready queue schema/capacity mismatch")
	}
	queue.next = snapshot.NextSequence
	queue.entries = snapshot.Entries
	if queue.pendingLocked() > capacity {
		return nil, errors.New("durable ready queue exceeds configured capacity")
	}
	seen := make(map[string]bool)
	for index := range queue.entries {
		id := gatewayv2.OperationIDString(queue.entries[index].Result.OperationID)
		if id == "" || seen[id] {
			return nil, errors.New("ready queue contains empty/duplicate operation ID")
		}
		seen[id] = true
		if queue.entries[index].State == DeliveryInFlight {
			queue.entries[index].State = DeliveryReady
		}
	}
	sort.SliceStable(queue.entries, func(i, j int) bool { return queue.entries[i].Sequence < queue.entries[j].Sequence })
	if err := queue.persistLocked(); err != nil {
		return nil, err
	}
	return queue, nil
}

func (q *DurableReadyQueue) persistLocked() error {
	if err := os.MkdirAll(filepath.Dir(q.path), 0o700); err != nil {
		return err
	}
	temporary := q.path + ".next"
	snapshot := readySnapshot{Schema: "gateway-v7-ready-queue-v1", Capacity: q.capacity,
		NextSequence: q.next, Entries: q.entries}
	raw, err := json.Marshal(snapshot)
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
	return os.Rename(temporary, q.path)
}

func (q *DurableReadyQueue) pendingLocked() int {
	pending := 0
	for _, entry := range q.entries {
		if entry.State != DeliveryDelivered {
			pending++
		}
	}
	return pending
}

func (q *DurableReadyQueue) Enqueue(result gatewayv2.ResultRecord, publishedNS int64) (bool, error) {
	q.mu.Lock()
	defer q.mu.Unlock()
	id := gatewayv2.OperationIDString(result.OperationID)
	if id == "" {
		return false, errors.New("cannot enqueue result without operation ID")
	}
	for _, entry := range q.entries {
		if gatewayv2.OperationIDString(entry.Result.OperationID) == id {
			return false, nil
		}
	}
	if q.pendingLocked() >= q.capacity {
		return false, errors.New("PROFILE_OVERFLOW: durable ready queue capacity exhausted")
	}
	q.entries = append(q.entries, ReadyEntry{Sequence: q.next, Result: result,
		State: DeliveryReady, PublishedNS: publishedNS})
	q.next++
	if err := q.persistLocked(); err != nil {
		q.entries = q.entries[:len(q.entries)-1]
		q.next--
		return false, err
	}
	return true, nil
}

// ReserveEligible selects the oldest ready result whose request session is no
// later than the current public session.  Later completions may bypass an
// ineligible future-session entry; publication order is private state.
func (q *DurableReadyQueue) ReserveEligible(publicSession, publicSlot uint32) (*gatewayv2.ResultRecord, error) {
	q.mu.Lock()
	defer q.mu.Unlock()
	selected := -1
	for index, entry := range q.entries {
		if entry.State == DeliveryReady && entry.Result.Session <= publicSession {
			if selected < 0 || entry.Sequence < q.entries[selected].Sequence {
				selected = index
			}
		}
	}
	if selected < 0 {
		return nil, nil
	}
	q.entries[selected].State = DeliveryInFlight
	q.entries[selected].PublicSession = publicSession
	q.entries[selected].PublicSlot = publicSlot
	q.entries[selected].DeliveryAttempt++
	if err := q.persistLocked(); err != nil {
		q.entries[selected].State = DeliveryReady
		q.entries[selected].DeliveryAttempt--
		return nil, err
	}
	result := q.entries[selected].Result
	return &result, nil
}

func (q *DurableReadyQueue) MarkDelivered(operationID string) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	for index := range q.entries {
		if gatewayv2.OperationIDString(q.entries[index].Result.OperationID) == operationID {
			if q.entries[index].State == DeliveryDelivered {
				return nil
			}
			if q.entries[index].State != DeliveryInFlight {
				return errors.New("result was not reserved for delivery")
			}
			q.entries[index].State = DeliveryDelivered
			return q.persistLocked()
		}
	}
	return errors.New("unknown delivery operation ID")
}

func (q *DurableReadyQueue) Pending() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return q.pendingLocked()
}

func (q *DurableReadyQueue) Entries() []ReadyEntry {
	q.mu.Lock()
	defer q.mu.Unlock()
	result := make([]ReadyEntry, len(q.entries))
	copy(result, q.entries)
	return result
}
