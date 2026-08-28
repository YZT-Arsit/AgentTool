package gatewayv2

import (
	"path/filepath"
	"testing"
)

func TestSPSCRingFixedRecords(t *testing.T) {
	path := filepath.Join(t.TempDir(), "ring.bin")
	producer, err := CreateRing(path, 4, 32)
	if err != nil {
		t.Fatal(err)
	}
	defer producer.Close()
	consumer, err := OpenRing(path)
	if err != nil {
		t.Fatal(err)
	}
	defer consumer.Close()
	record := make([]byte, 32)
	for index := range record {
		record[index] = byte(index)
	}
	if !producer.TryPush(record) {
		t.Fatal("push failed")
	}
	out := make([]byte, 32)
	if !consumer.TryPop(out) {
		t.Fatal("pop failed")
	}
	for index := range record {
		if out[index] != record[index] {
			t.Fatalf("byte %d changed", index)
		}
	}
	if consumer.TryPop(out) {
		t.Fatal("empty ring produced a record")
	}
}
