package v7

import (
	"path/filepath"
	"strconv"
	"testing"

	gatewayv2 "common-action-gateway-v2"
)

func result(id string, requestSession uint32) gatewayv2.ResultRecord {
	value := gatewayv2.ResultRecord{Session: requestSession, RequestSlot: 1,
		Status: gatewayv2.StatusOK, OperationID: gatewayv2.OperationID(id), PayloadLen: uint16(len(id))}
	copy(value.Payload[:], []byte(id))
	return value
}

func TestDurableQueueSurvivesCrashBeforePublicSend(t *testing.T) {
	path := filepath.Join(t.TempDir(), "ready.json")
	queue, err := OpenDurableReadyQueue(path, 10)
	if err != nil {
		t.Fatal(err)
	}
	if inserted, err := queue.Enqueue(result("late", 0), 10); err != nil || !inserted {
		t.Fatalf("inserted=%v err=%v", inserted, err)
	}
	reserved, err := queue.ReserveEligible(1, 1)
	if err != nil || reserved == nil {
		t.Fatalf("reserve=%v err=%v", reserved, err)
	}

	// Simulated process death after durable reservation and before socket send.
	restarted, err := OpenDurableReadyQueue(path, 10)
	if err != nil {
		t.Fatal(err)
	}
	replay, err := restarted.ReserveEligible(2, 1)
	if err != nil || replay == nil || gatewayv2.OperationIDString(replay.OperationID) != "late" {
		t.Fatalf("replay=%v err=%v", replay, err)
	}
}

func TestDurableQueueCrashAfterSendBeforeAckReplaysForTrustedDedup(t *testing.T) {
	path := filepath.Join(t.TempDir(), "ready.json")
	queue, _ := OpenDurableReadyQueue(path, 10)
	_, _ = queue.Enqueue(result("ambiguous-send", 0), 10)
	reserved, _ := queue.ReserveEligible(0, 1)
	if reserved == nil {
		t.Fatal("result not reserved")
	}
	// Socket send occurred, but MarkDelivered did not. Recovery intentionally
	// retries; the trusted client must suppress duplicate operation IDs.
	restarted, _ := OpenDurableReadyQueue(path, 10)
	replay, _ := restarted.ReserveEligible(0, 2)
	if replay == nil || gatewayv2.OperationIDString(replay.OperationID) != "ambiguous-send" {
		t.Fatal("ambiguous public send was silently lost")
	}
}

func TestDurableQueueOutOfOrderAndLateEligibility(t *testing.T) {
	queue, _ := OpenDurableReadyQueue(filepath.Join(t.TempDir(), "ready.json"), 10)
	_, _ = queue.Enqueue(result("future", 4), 10)
	_, _ = queue.Enqueue(result("eligible", 1), 20)
	selected, err := queue.ReserveEligible(2, 3)
	if err != nil || selected == nil || gatewayv2.OperationIDString(selected.OperationID) != "eligible" {
		t.Fatalf("selected=%v err=%v", selected, err)
	}
	if err := queue.MarkDelivered("eligible"); err != nil {
		t.Fatal(err)
	}
	if selected, _ := queue.ReserveEligible(3, 1); selected != nil {
		t.Fatal("future result leaked into an earlier public session")
	}
	selected, _ = queue.ReserveEligible(4, 1)
	if selected == nil || gatewayv2.OperationIDString(selected.OperationID) != "future" {
		t.Fatal("future result did not become eligible")
	}
}

func TestDurableQueueDeduplicatesAndFailsClosedAtCapacity(t *testing.T) {
	queue, _ := OpenDurableReadyQueue(filepath.Join(t.TempDir(), "ready.json"), 2)
	inserted, _ := queue.Enqueue(result("a", 0), 1)
	if !inserted {
		t.Fatal("first insert rejected")
	}
	inserted, err := queue.Enqueue(result("a", 0), 2)
	if err != nil || inserted {
		t.Fatalf("duplicate inserted=%v err=%v", inserted, err)
	}
	_, _ = queue.Enqueue(result("b", 0), 3)
	if _, err := queue.Enqueue(result("c", 0), 4); err == nil {
		t.Fatal("capacity overflow was not explicit")
	}
}

func TestDeliveryOfOneTenFiftyAndOneHundredOperations(t *testing.T) {
	for _, count := range []int{1, 10, 50, 100} {
		t.Run(strconv.Itoa(count), func(t *testing.T) {
			queue, _ := OpenDurableReadyQueue(filepath.Join(t.TempDir(), "ready.json"), count)
			// Reverse publication models out-of-order provider completion.
			for index := count - 1; index >= 0; index-- {
				id := fmtID(index)
				if _, err := queue.Enqueue(result(id, uint32(index%3)), int64(count-index)); err != nil {
					t.Fatal(err)
				}
			}
			delivered := make(map[string]bool)
			for slot := 0; slot < count+3; slot++ {
				selected, err := queue.ReserveEligible(uint32(slot), uint32(slot+1))
				if err != nil {
					t.Fatal(err)
				}
				if selected == nil {
					continue
				}
				id := gatewayv2.OperationIDString(selected.OperationID)
				if delivered[id] {
					t.Fatalf("duplicate framework delivery: %s", id)
				}
				delivered[id] = true
				if err := queue.MarkDelivered(id); err != nil {
					t.Fatal(err)
				}
			}
			if len(delivered) != count || queue.Pending() != 0 {
				t.Fatalf("delivered=%d pending=%d want=%d", len(delivered), queue.Pending(), count)
			}
		})
	}
}

func fmtID(index int) string {
	return "op-" + strconv.Itoa(index)
}
