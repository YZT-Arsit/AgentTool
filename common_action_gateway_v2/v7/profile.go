package v7

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
)

type PublicTerminalStatus string

const (
	StatusDelivered       PublicTerminalStatus = "DELIVERED"
	StatusLateDeliverable PublicTerminalStatus = "LATE_BUT_DELIVERABLE"
	StatusProfileOverflow PublicTerminalStatus = "PROFILE_OVERFLOW"
	StatusProviderTimeout PublicTerminalStatus = "PROVIDER_TIMEOUT"
	StatusGatewayFailure  PublicTerminalStatus = "GATEWAY_FAILURE"
	StatusEffectUnknown   PublicTerminalStatus = "EFFECT_OUTCOME_UNKNOWN"
)

// AdmissionProfile is public. AdmissionSlots reserve the leading request slots
// that may contain real work; the remaining slots form a secret-independent
// continuation tail. One result can be carried by each public response slot.
type AdmissionProfile struct {
	Sessions                  int   `json:"sessions"`
	SlotsPerSession           int   `json:"slots_per_session"`
	AdmissionSlots            int   `json:"admission_slots"`
	MaxRealOperations         int   `json:"max_real_operations"`
	SlotIntervalNS            int64 `json:"slot_interval_ns"`
	ProviderCompletionBoundNS int64 `json:"provider_completion_bound_ns"`
	TerminalSlots             int   `json:"terminal_slots"`
}

func (p AdmissionProfile) TotalSlots() int        { return p.Sessions * p.SlotsPerSession }
func (p AdmissionProfile) ContinuationSlots() int { return p.TotalSlots() - p.AdmissionSlots }

func (p AdmissionProfile) Validate() error {
	if p.Sessions < 1 || p.SlotsPerSession < 1 || p.SlotIntervalNS <= 0 {
		return errors.New("invalid public profile dimensions")
	}
	if p.AdmissionSlots < 0 || p.AdmissionSlots > p.TotalSlots() {
		return errors.New("admission slots outside public schedule")
	}
	if p.MaxRealOperations < 0 || p.MaxRealOperations > p.AdmissionSlots {
		return errors.New("real-operation bound exceeds public admission slots")
	}
	if p.ProviderCompletionBoundNS < 0 {
		return errors.New("negative provider-completion bound")
	}
	// Worst case: all operations become ready at the declared completion bound
	// after the last admission. The continuation tail must then have enough time
	// for that bound and enough response slots to drain all admitted results.
	completionSlots := int((p.ProviderCompletionBoundNS + p.SlotIntervalNS - 1) / p.SlotIntervalNS)
	if p.TerminalSlots < 1 {
		return errors.New("at least one public terminal-status slot is required")
	}
	required := completionSlots + p.MaxRealOperations + p.TerminalSlots
	if p.ContinuationSlots() < required {
		return fmt.Errorf("public tail has %d slots; requires %d (%d completion + %d drain)",
			p.ContinuationSlots(), required, completionSlots, p.MaxRealOperations)
	}
	return nil
}

func LoadAdmissionProfile(path string) (AdmissionProfile, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return AdmissionProfile{}, err
	}
	var profile AdmissionProfile
	if err := json.Unmarshal(raw, &profile); err != nil {
		return AdmissionProfile{}, err
	}
	return profile, profile.Validate()
}

func (p AdmissionProfile) Admit(realOperations int) error {
	if err := p.Validate(); err != nil {
		return err
	}
	if realOperations > p.MaxRealOperations {
		return fmt.Errorf("PROFILE_OVERFLOW: %d operations exceed public bound %d", realOperations, p.MaxRealOperations)
	}
	return nil
}

func (p AdmissionProfile) ClassifyCompletion(admissionSlot, completionSlot int) PublicTerminalStatus {
	if completionSlot >= p.TotalSlots() {
		return StatusProfileOverflow
	}
	if completionSlot > admissionSlot {
		return StatusLateDeliverable
	}
	return StatusDelivered
}
