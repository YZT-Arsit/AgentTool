package canonicalv9

import (
	"testing"
	"time"
)

func TestV12AbsolutePacerDeadlineAndMissRules(t *testing.T) {
	period := int64(10 * time.Millisecond)
	t0 := int64(100 * time.Millisecond)
	dispatches := []int64{
		t0,
		t0 + period + int64(5*time.Millisecond),
		t0 + 2*period + int64(35*time.Millisecond),
		t0 + 2*period + int64(35*time.Millisecond),
		t0 + 2*period + int64(35*time.Millisecond),
		t0 + 2*period + int64(35*time.Millisecond),
	}
	decisions := evaluateAbsoluteSlots(t0, period, dispatches)
	if len(decisions) != len(dispatches) {
		t.Fatalf("fixed public slot count changed: got=%d want=%d", len(decisions), len(dispatches))
	}
	for index, decision := range decisions {
		want := t0 + int64(index)*period
		if decision.DeadlineNS != want {
			t.Fatalf("absolute deadline drift at slot %d: got=%d want=%d", index+1, decision.DeadlineNS, want)
		}
	}
	if decisions[1].Missed || !decisions[1].Transmit {
		t.Fatal("5 ms wake delay under 10 ms period was not diagnostic-only")
	}
	for _, index := range []int{2, 3, 4} {
		if !decisions[index].Missed || decisions[index].Transmit {
			t.Fatalf("expired slot %d was not failed closed: %+v", index+1, decisions[index])
		}
	}
	if decisions[5].Missed || !decisions[5].Transmit {
		t.Fatalf("first non-expired absolute slot was not eligible: %+v", decisions[5])
	}
	transmittedAtDelayedInstant := 0
	for _, decision := range decisions[2:] {
		if decision.DispatchNS == dispatches[2] && decision.Transmit {
			transmittedAtDelayedInstant++
		}
	}
	if transmittedAtDelayedInstant != 1 {
		t.Fatalf("catch-up burst allowed %d transmissions at one delayed instant", transmittedAtDelayedInstant)
	}
}

func TestV12PublicPacerUsesAbsoluteDeadlineContract(t *testing.T) {
	pacer, err := newPublicPacer()
	if err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(2 * time.Millisecond)
	if err := pacer.WaitUntil(deadline); err != nil {
		t.Fatal(err)
	}
	configuration := pacer.Close()
	if !configuration.AbsoluteDeadlines || !configuration.OSThreadLocked {
		t.Fatalf("pacer contract incomplete: %+v", configuration)
	}
	if time.Now().Before(deadline) {
		t.Fatal("absolute pacer returned before deadline")
	}
}
