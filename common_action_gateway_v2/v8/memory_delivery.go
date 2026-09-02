package v8

import (
	"errors"
	"io"
	"sync"

	gatewayv2 "common-action-gateway-v2"
)

type MemoryDeliveryEntry struct {
	Sequence uint64
	Result   gatewayv2.ResultRecord
	Reserved bool
}

// MemoryDeliveryQueue contains only results that the worker/durability plane
// has already committed. It performs no filesystem I/O.
type MemoryDeliveryQueue struct {
	mu       sync.Mutex
	capacity int
	next     uint64
	entries  []MemoryDeliveryEntry
}

func NewMemoryDeliveryQueue(capacity int) (*MemoryDeliveryQueue, error) {
	if capacity < 1 {
		return nil, errors.New("memory delivery capacity must be positive")
	}
	return &MemoryDeliveryQueue{capacity: capacity, entries: make([]MemoryDeliveryEntry, 0, capacity)}, nil
}

func (q *MemoryDeliveryQueue) PublishDurable(result gatewayv2.ResultRecord) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	if len(q.entries) >= q.capacity {
		return errors.New("in-memory delivery capacity exhausted")
	}
	q.entries = append(q.entries, MemoryDeliveryEntry{Sequence: q.next, Result: result})
	q.next++
	return nil
}

func (q *MemoryDeliveryQueue) SnapshotEligible(publicSession uint32) *gatewayv2.ResultRecord {
	q.mu.Lock()
	defer q.mu.Unlock()
	selected := -1
	for index := range q.entries {
		entry := &q.entries[index]
		if !entry.Reserved && entry.Result.Session <= publicSession &&
			(selected < 0 || entry.Sequence < q.entries[selected].Sequence) {
			selected = index
		}
	}
	if selected < 0 {
		return nil
	}
	q.entries[selected].Reserved = true
	result := q.entries[selected].Result
	return &result
}

// PreparedSlot is immutable response bytes produced before the public deadline.
// Send performs one writer call and one nonblocking in-memory acknowledgement.
type PreparedSlot struct {
	Frame       []byte
	OperationID string
	Ack         chan string
}

func (p PreparedSlot) Send(writer io.Writer) error {
	written, err := writer.Write(p.Frame)
	if err != nil {
		return err
	}
	if written != len(p.Frame) {
		return io.ErrShortWrite
	}
	if p.OperationID != "" && p.Ack != nil {
		select {
		case p.Ack <- p.OperationID:
		default:
			return errors.New("delivery acknowledgement backpressure after public send")
		}
	}
	return nil
}
