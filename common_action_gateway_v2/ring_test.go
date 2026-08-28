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

func TestResultRingSaturationFailsClosedWithoutOverwrite(t *testing.T) {
	path := t.TempDir() + "/saturation.shared"
	ring, err := CreateRing(path, 2, InternalResultBytes)
	if err != nil {
		t.Fatal(err)
	}
	defer ring.Close()
	first := make([]byte, InternalResultBytes)
	first[0] = 7
	second := make([]byte, InternalResultBytes)
	second[0] = 8
	third := make([]byte, InternalResultBytes)
	third[0] = 9
	if !ring.TryPush(first) || !ring.TryPush(second) {
		t.Fatal("ring did not accept capacity")
	}
	if ring.TryPush(third) {
		t.Fatal("saturated ring silently overwrote a pending result")
	}
	out := make([]byte, InternalResultBytes)
	if !ring.TryPop(out) || out[0] != 7 {
		t.Fatal("saturation corrupted oldest result")
	}
}
