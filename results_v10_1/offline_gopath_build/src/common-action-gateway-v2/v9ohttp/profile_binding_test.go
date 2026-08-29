package v9ohttp

import (
	"testing"

	"common-action-gateway-v2/v7"
	"common-action-gateway-v2/v8"
)

func TestV9RuntimeAdmissionBindingFailsClosedForEveryPublicCapacityInput(t *testing.T) {
	profile := v8.ScheduleProfile{
		ProfileID: "V9-BOUND", Sessions: 2, SlotsPerSession: 64,
		RequestFinalBytes: 1079, ResponseFinalBytes: 800,
		RequestIntervalNS: 10_000_000, ResponseSlotIntervalNS: 10_000_000,
		PublicLifetimeNS: 1_280_000_000, MaximumAdmittedOperations: 10,
		TerminalSlots: 1, ProviderCompletionBoundNS: 100_000_000,
		RelayEndpoint: "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY", ConnectionPolicy: "KEEP_ALIVE",
		OHTTPSuite: v8.OHTTPPublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001, ConfigEpoch: 3},
	}
	admission := v7.AdmissionProfile{
		Sessions: 2, SlotsPerSession: 64, AdmissionSlots: 10, MaxRealOperations: 10,
		SlotIntervalNS: 10_000_000, ProviderCompletionBoundNS: 100_000_000, TerminalSlots: 1,
	}
	if err := v8.BindAdmission(profile, admission); err != nil {
		t.Fatal(err)
	}

	tests := map[string]func(*v8.ScheduleProfile, *v7.AdmissionProfile){
		"sessions":          func(_ *v8.ScheduleProfile, a *v7.AdmissionProfile) { a.Sessions++ },
		"slots_per_session": func(_ *v8.ScheduleProfile, a *v7.AdmissionProfile) { a.SlotsPerSession++ },
		"slot_interval":     func(_ *v8.ScheduleProfile, a *v7.AdmissionProfile) { a.SlotIntervalNS++ },
		"max_operations":    func(_ *v8.ScheduleProfile, a *v7.AdmissionProfile) { a.MaxRealOperations-- },
		"terminal_slots":    func(_ *v8.ScheduleProfile, a *v7.AdmissionProfile) { a.TerminalSlots++ },
		"completion_bound":  func(_ *v8.ScheduleProfile, a *v7.AdmissionProfile) { a.ProviderCompletionBoundNS++ },
		"public_lifetime":   func(p *v8.ScheduleProfile, _ *v7.AdmissionProfile) { p.PublicLifetimeNS-- },
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			changedProfile := profile
			changedAdmission := admission
			mutate(&changedProfile, &changedAdmission)
			if v8.BindAdmission(changedProfile, changedAdmission) == nil {
				t.Fatal("mismatched runtime/admission configuration was accepted")
			}
		})
	}
}
