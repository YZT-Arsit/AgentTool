package v7

// This package is the V7 functional-closure layer.  It imports the frozen V6
// wire/result types, but does not modify the content-addressed V6 implementation.

import (
	"bytes"
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

type readyLogRecord struct {
	Schema       string     `json:"schema"`
	Capacity     int        `json:"capacity"`
	NextSequence uint64     `json:"next_sequence"`
	Entry        ReadyEntry `json:"entry"`
}

const readyWALSchema = "gateway-v7-ready-queue-wal-v1"

// DurableReadyQueue is a bounded private queue. Publication and delivered-state
// transitions are append-only and fsync'd. IN_FLIGHT is intentionally ephemeral:
// after restart the durable READY record is replayed because duplicate delivery
// is safe under trusted-client operation_id deduplication, while loss is not.
type DurableReadyQueue struct {
	mu       sync.Mutex
	path     string
	capacity int
	next     uint64
	entries  []ReadyEntry
	wal      bool
}

func OpenDurableReadyQueue(path string, capacity int) (*DurableReadyQueue, error) {
	if capacity < 1 {
		return nil, errors.New("ready queue capacity must be positive")
	}
	queue := &DurableReadyQueue{path: path, capacity: capacity, wal: true}
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return queue, nil
		}
		return nil, err
	}
	var snapshot readySnapshot
	if err := json.Unmarshal(raw, &snapshot); err == nil && snapshot.Schema == "gateway-v7-ready-queue-v1" {
		if snapshot.Capacity != capacity {
			return nil, errors.New("ready queue schema/capacity mismatch")
		}
		queue.next = snapshot.NextSequence
		queue.entries = snapshot.Entries
		queue.wal = false // Legacy snapshot; migrate atomically on first mutation.
	} else {
		for lineNumber, line := range bytes.Split(raw, []byte{'\n'}) {
			if len(bytes.TrimSpace(line)) == 0 {
				continue
			}
			var record readyLogRecord
			if err := json.Unmarshal(line, &record); err != nil || record.Schema != readyWALSchema ||
				record.Capacity != capacity || gatewayv2.OperationIDString(record.Entry.Result.OperationID) == "" {
				return nil, fmt.Errorf("ready queue integrity/format error at WAL line %d", lineNumber+1)
			}
			queue.next = record.NextSequence
			id := gatewayv2.OperationIDString(record.Entry.Result.OperationID)
			updated := false
			for index := range queue.entries {
				if gatewayv2.OperationIDString(queue.entries[index].Result.OperationID) == id {
					queue.entries[index] = record.Entry
					updated = true
					break
				}
			}
			if !updated {
				queue.entries = append(queue.entries, record.Entry)
			}
		}
	}
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
	return queue, nil
}

func (q *DurableReadyQueue) ensureWALLocked() error {
	if q.wal {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(q.path), 0o700); err != nil {
		return err
	}
	temporary := q.path + ".next"
	file, err := os.OpenFile(temporary, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	entries := append([]ReadyEntry(nil), q.entries...)
	sort.SliceStable(entries, func(i, j int) bool { return entries[i].Sequence < entries[j].Sequence })
	encoder := json.NewEncoder(file)
	for _, entry := range entries {
		if err = encoder.Encode(readyLogRecord{Schema: readyWALSchema, Capacity: q.capacity,
			NextSequence: q.next, Entry: entry}); err != nil {
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
	if err := os.Rename(temporary, q.path); err != nil {
		return err
	}
	q.wal = true
	return nil
}

func (q *DurableReadyQueue) persistEntryLocked(entry ReadyEntry) error {
	if err := q.ensureWALLocked(); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(q.path), 0o700); err != nil {
		return err
	}
	file, err := os.OpenFile(q.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	err = json.NewEncoder(file).Encode(readyLogRecord{Schema: readyWALSchema, Capacity: q.capacity,
		NextSequence: q.next, Entry: entry})
	if err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err != nil {
		return err
	}
	return closeErr
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
	if err := q.persistEntryLocked(q.entries[len(q.entries)-1]); err != nil {
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
	return q.reserveEligible(publicSession, publicSlot, 0)
}

// ReserveEligibleBefore commits a public response slot using only results that
// were durably published by its frozen public logical cutoff. The caller may
// derive that cutoff from a nominal or a secret-independent effective public
// clock. A zero cutoff retains the legacy behavior.
func (q *DurableReadyQueue) ReserveEligibleBefore(publicSession, publicSlot uint32, cutoffNS int64) (*gatewayv2.ResultRecord, error) {
	if cutoffNS <= 0 {
		return nil, errors.New("result commitment cutoff must be positive")
	}
	return q.reserveEligible(publicSession, publicSlot, cutoffNS)
}

func (q *DurableReadyQueue) reserveEligible(publicSession, publicSlot uint32, cutoffNS int64) (*gatewayv2.ResultRecord, error) {
	q.mu.Lock()
	defer q.mu.Unlock()
	selected := -1
	for index, entry := range q.entries {
		eligibleByTime := cutoffNS == 0 || entry.PublishedNS <= cutoffNS
		if entry.State == DeliveryReady && entry.Result.Session <= publicSession && eligibleByTime {
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
	// IN_FLIGHT is intentionally in-memory only. If the process crashes before
	// delivery acknowledgement, the last durable READY record is replayed; the
	// trusted client deduplicates by operation_id, so replay is safer than loss.
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
			previous := q.entries[index]
			q.entries[index].State = DeliveryDelivered
			if err := q.persistEntryLocked(q.entries[index]); err != nil {
				q.entries[index] = previous
				return err
			}
			return nil
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
