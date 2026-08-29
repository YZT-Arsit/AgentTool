// Package v8 contains transport-independent V8 closure repairs. It does not
// implement RFC 9458 or RFC 9292 cryptography.
package v8

import (
	"errors"
	"fmt"

	v7 "common-action-gateway-v2/v7"
)

type OHTTPPublicSuite struct {
	KeyID       uint8  `json:"key_id"`
	KEMID       uint16 `json:"kem_id"`
	KDFID       uint16 `json:"kdf_id"`
	AEADID      uint16 `json:"aead_id"`
	ConfigEpoch uint64 `json:"config_epoch"`
}

type ScheduleProfile struct {
	ProfileID                 string           `json:"profile_id"`
	Sessions                  int              `json:"sessions"`
	SlotsPerSession           int              `json:"slots_per_session"`
	RequestFinalBytes         int              `json:"request_final_bytes"`
	ResponseFinalBytes        int              `json:"response_final_bytes"`
	RequestIntervalNS         int64            `json:"request_interval_ns"`
	ResponseSlotIntervalNS    int64            `json:"response_slot_interval_ns"`
	ResponseLagNS             int64            `json:"response_lag_ns"`
	PublicLifetimeNS          int64            `json:"public_lifetime_ns"`
	MaximumAdmittedOperations int              `json:"maximum_admitted_operations"`
	TerminalSlots             int              `json:"terminal_slots"`
	ProviderCompletionBoundNS int64            `json:"provider_completion_bound_ns"`
	RelayEndpoint             string           `json:"relay_endpoint"`
	GatewayEndpoint           string           `json:"gateway_endpoint"`
	ConnectionPolicy          string           `json:"connection_policy"`
	OHTTPSuite                OHTTPPublicSuite `json:"ohttp_suite"`
}

func (p ScheduleProfile) Validate() error {
	if p.ProfileID == "" || p.Sessions < 1 || p.SlotsPerSession < 1 {
		return errors.New("invalid public schedule dimensions")
	}
	if p.RequestFinalBytes < 1 || p.ResponseFinalBytes < 1 || p.RequestIntervalNS <= 0 || p.ResponseSlotIntervalNS <= 0 {
		return errors.New("public sizes and intervals must be positive")
	}
	if p.ResponseLagNS < 0 || p.PublicLifetimeNS <= 0 || p.MaximumAdmittedOperations < 0 {
		return errors.New("invalid public lifetime/admission values")
	}
	if p.RelayEndpoint == "" || p.GatewayEndpoint == "" || p.ConnectionPolicy == "" {
		return errors.New("public endpoints/connection policy are required")
	}
	return nil
}

// BindAdmission mechanically ties every capacity proof input to the exact
// scheduler profile used by the public slot implementation.
func BindAdmission(profile ScheduleProfile, admission v7.AdmissionProfile) error {
	if err := profile.Validate(); err != nil {
		return err
	}
	if admission.Sessions != profile.Sessions || admission.SlotsPerSession != profile.SlotsPerSession {
		return errors.New("admission and public schedule dimensions differ")
	}
	if admission.SlotIntervalNS != profile.ResponseSlotIntervalNS {
		return errors.New("admission interval differs from actual response-slot interval")
	}
	if admission.MaxRealOperations != profile.MaximumAdmittedOperations ||
		admission.TerminalSlots != profile.TerminalSlots ||
		admission.ProviderCompletionBoundNS != profile.ProviderCompletionBoundNS {
		return errors.New("admission capacity inputs differ from public profile")
	}
	if expected := int64(profile.Sessions*profile.SlotsPerSession) * profile.ResponseSlotIntervalNS; profile.PublicLifetimeNS < expected {
		return fmt.Errorf("public lifetime %d is shorter than response schedule %d", profile.PublicLifetimeNS, expected)
	}
	return admission.Validate()
}
