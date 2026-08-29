package v7

import "testing"

func TestPublicAdmissionRequiresCompletionAndDrainTail(t *testing.T) {
	profile := AdmissionProfile{Sessions: 1, SlotsPerSession: 160, AdmissionSlots: 50,
		MaxRealOperations: 50, SlotIntervalNS: 10, ProviderCompletionBoundNS: 500, TerminalSlots: 1}
	if err := profile.Validate(); err != nil {
		t.Fatal(err)
	}
	if err := profile.Admit(50); err != nil {
		t.Fatal(err)
	}
	if err := profile.Admit(51); err == nil {
		t.Fatal("over-admission did not fail closed")
	}
}

func TestV6LikeProfileFailsCapacityProof(t *testing.T) {
	profile := AdmissionProfile{Sessions: 50, SlotsPerSession: 3, AdmissionSlots: 148,
		MaxRealOperations: 50, SlotIntervalNS: 15_000_000, ProviderCompletionBoundNS: 400_000_000, TerminalSlots: 1}
	if err := profile.Validate(); err == nil {
		t.Fatal("V6-like schedule unexpectedly proved sufficient")
	}
}

func TestPublicTerminalStatuses(t *testing.T) {
	profile := AdmissionProfile{Sessions: 1, SlotsPerSession: 20, AdmissionSlots: 5,
		MaxRealOperations: 5, SlotIntervalNS: 10, ProviderCompletionBoundNS: 50, TerminalSlots: 1}
	if got := profile.ClassifyCompletion(1, 1); got != StatusDelivered {
		t.Fatal(got)
	}
	if got := profile.ClassifyCompletion(1, 8); got != StatusLateDeliverable {
		t.Fatal(got)
	}
	if got := profile.ClassifyCompletion(1, 20); got != StatusProfileOverflow {
		t.Fatal(got)
	}
}
