package canonicalv9

import (
	"bytes"
	"errors"
	"fmt"
	"time"

	"common-action-gateway-v2/v7"
	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v8"
	"common-action-gateway-v2/v9ohttp"
	ohttp "github.com/chris-wood/ohttp-go"
)

type SizeMatrixRow struct {
	Direction    string `json:"direction"`
	Variant      string `json:"variant"`
	BHTTPBytes   int    `json:"bhttp_bytes"`
	OHTTPBytes   int    `json:"ohttp_bytes"`
	ExpectedSize int    `json:"expected_size"`
	Pass         bool   `json:"pass"`
}

type AdmissionCheck struct {
	Case             string `json:"case"`
	ExpectedAccepted bool   `json:"expected_accepted"`
	Accepted         bool   `json:"accepted"`
	Pass             bool   `json:"pass"`
	Error            string `json:"error,omitempty"`
}

type DiagnosticsResult struct {
	SizeMatrix             []SizeMatrixRow  `json:"size_matrix"`
	AdmissionBinding       []AdmissionCheck `json:"admission_binding"`
	AllWireSizesPass       bool             `json:"all_wire_sizes_pass"`
	AllAdmissionChecksPass bool             `json:"all_admission_checks_pass"`
}

func diagnosticCrypto() (*v9ohttp.RFC9458Client, *v9ohttp.RFC9458Gateway, error) {
	private, err := ohttp.NewConfig(7, 0x0020, 0x0001, 0x0001)
	if err != nil {
		return nil, nil, err
	}
	suite := v9ohttp.PublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001,
		ConfigurationEpoch: 3, AuthenticatedSource: "V9_CANONICAL_LOCAL"}
	client, err := v9ohttp.NewRFC9458Client(private.Config(), suite)
	if err != nil {
		return nil, nil, err
	}
	gateway, err := v9ohttp.NewRFC9458Gateway(private, suite)
	return client, gateway, err
}

func MeasureSizeMatrix(plan Plan) ([]SizeMatrixRow, error) {
	codec := v9ohttp.RFC9292Codec{}
	client, gateway, err := diagnosticCrypto()
	if err != nil {
		return nil, err
	}
	requests := []struct {
		name string
		msg  v7ohttp.PrivateActionMessage
	}{
		{"NOOP", v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionNoop, OperationID: []byte("size-noop")}},
		{"TOOL", v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionRealTool, RouteHandle: bytes.Repeat([]byte{'r'}, 32), OperationID: bytes.Repeat([]byte{'o'}, 32), ProtectedArgs: bytes.Repeat([]byte{'a'}, 128), Authorization: bytes.Repeat([]byte{'z'}, 128)}},
		{"AGENT_SERVICE", v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionAgentService, RouteHandle: bytes.Repeat([]byte{'r'}, 32), OperationID: bytes.Repeat([]byte{'o'}, 32), ProtectedArgs: bytes.Repeat([]byte{'a'}, 128), Authorization: bytes.Repeat([]byte{'z'}, 128)}},
		{"EXTERNAL_HTTP", v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionExternalHTTP, RouteHandle: bytes.Repeat([]byte{'r'}, 32), OperationID: bytes.Repeat([]byte{'o'}, 32), ProtectedArgs: bytes.Repeat([]byte{'a'}, 128), Authorization: bytes.Repeat([]byte{'z'}, 128)}},
	}
	rows := make([]SizeMatrixRow, 0, len(requests)+6)
	for index, variant := range requests {
		bhttp, err := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, variant.msg, plan.RequestBHTTPBytes)
		if err != nil {
			return nil, fmt.Errorf("request size variant %s: %w", variant.name, err)
		}
		wire, _, err := client.EncapsulateRequest(v7ohttp.SlotID{Session: 9, Slot: uint32(index + 1)}, bhttp)
		if err != nil {
			return nil, err
		}
		rows = append(rows, SizeMatrixRow{"REQUEST", variant.name, len(bhttp), len(wire), plan.RequestFinalBytes, len(wire) == plan.RequestFinalBytes})
	}
	responses := []struct {
		name   string
		status byte
	}{
		{"WAIT", v9ohttp.StatusWait}, {"RESULT", v9ohttp.StatusResult}, {"ERROR", v9ohttp.StatusError},
		{"TIMEOUT", v9ohttp.StatusTimeout}, {"EFFECT_OUTCOME_UNKNOWN", v9ohttp.StatusEffectOutcomeUnknown},
		{"PROFILE_OVERFLOW", v9ohttp.StatusProfileOverflow},
	}
	for index, variant := range responses {
		slot := v7ohttp.SlotID{Session: 10, Slot: uint32(index + 1)}
		requestBHTTP, _ := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget,
			v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionNoop, OperationID: []byte(fmt.Sprintf("context-%d", index))}, plan.RequestBHTTPBytes)
		requestWire, clientContext, err := client.EncapsulateRequest(slot, requestBHTTP)
		if err != nil {
			return nil, err
		}
		_, serverContext, err := gateway.DecapsulateRequest(slot, requestWire)
		if err != nil || clientContext.Slot() != slot || serverContext.Slot() != slot {
			return nil, errors.New("diagnostic OHTTP context slot mismatch")
		}
		response := v7ohttp.PrivateResponse{Status: variant.status}
		if variant.status != v9ohttp.StatusWait {
			response.OperationID = "size-response-operation"
			response.Payload = bytes.Repeat([]byte{'p'}, 192)
		}
		bhttp, err := codec.EncodeKnownLengthResponse(response, plan.ResponseBHTTPBytes)
		if err != nil {
			return nil, fmt.Errorf("response size variant %s: %w", variant.name, err)
		}
		wire, err := gateway.EncapsulateResponse(serverContext, bhttp)
		if err != nil {
			return nil, err
		}
		opened, err := client.DecapsulateResponse(clientContext, wire)
		if err != nil || !bytes.Equal(opened, bhttp) {
			return nil, errors.New("diagnostic OHTTP response context failed")
		}
		rows = append(rows, SizeMatrixRow{"RESPONSE", variant.name, len(bhttp), len(wire), plan.ResponseFinalBytes, len(wire) == plan.ResponseFinalBytes})
	}
	return rows, nil
}

func canonicalProfiles(plan Plan) (v8.ScheduleProfile, v7.AdmissionProfile) {
	interval := int64(time.Duration(plan.RoundPeriodMS) * time.Millisecond)
	completion := int64(time.Duration(plan.ProviderCompletionBoundMS) * time.Millisecond)
	profile := v8.ScheduleProfile{ProfileID: plan.ProfileID, Sessions: 1, SlotsPerSession: plan.Rounds,
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes,
		RequestIntervalNS: interval, ResponseSlotIntervalNS: interval,
		PublicLifetimeNS: int64(plan.Rounds) * interval, MaximumAdmittedOperations: plan.MaximumRealOperations,
		TerminalSlots: 1, ProviderCompletionBoundNS: completion, RelayEndpoint: "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY",
		ConnectionPolicy: "KEEP_ALIVE", OHTTPSuite: v8.OHTTPPublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001, ConfigEpoch: 3}}
	admission := v7.AdmissionProfile{Sessions: 1, SlotsPerSession: plan.Rounds, AdmissionSlots: plan.AdmissionRounds,
		MaxRealOperations: plan.MaximumRealOperations, SlotIntervalNS: interval,
		ProviderCompletionBoundNS: completion, TerminalSlots: 1}
	return profile, admission
}

func AdmissionBindingValidation(plan Plan) []AdmissionCheck {
	type mutation struct {
		name   string
		accept bool
		apply  func(*v8.ScheduleProfile, *v7.AdmissionProfile)
	}
	cases := []mutation{
		{"MATCHED", true, func(*v8.ScheduleProfile, *v7.AdmissionProfile) {}},
		{"SESSIONS_MISMATCH", false, func(p *v8.ScheduleProfile, _ *v7.AdmissionProfile) { p.Sessions++ }},
		{"SLOTS_PER_SESSION_MISMATCH", false, func(p *v8.ScheduleProfile, _ *v7.AdmissionProfile) { p.SlotsPerSession++ }},
		{"RESPONSE_INTERVAL_MISMATCH", false, func(p *v8.ScheduleProfile, _ *v7.AdmissionProfile) { p.ResponseSlotIntervalNS++ }},
		{"MAX_ADMITTED_MISMATCH", false, func(p *v8.ScheduleProfile, _ *v7.AdmissionProfile) { p.MaximumAdmittedOperations++ }},
		{"CONTINUATION_CAPACITY_INSUFFICIENT", false, func(_ *v8.ScheduleProfile, a *v7.AdmissionProfile) { a.AdmissionSlots = a.TotalSlots() - 1 }},
		{"PUBLIC_LIFETIME_TOO_SHORT", false, func(p *v8.ScheduleProfile, _ *v7.AdmissionProfile) { p.PublicLifetimeNS-- }},
	}
	result := make([]AdmissionCheck, 0, len(cases))
	for _, item := range cases {
		profile, admission := canonicalProfiles(plan)
		item.apply(&profile, &admission)
		err := v8.BindAdmission(profile, admission)
		accepted := err == nil
		row := AdmissionCheck{Case: item.name, ExpectedAccepted: item.accept, Accepted: accepted, Pass: accepted == item.accept}
		if err != nil {
			row.Error = err.Error()
		}
		result = append(result, row)
	}
	return result
}

func Diagnostics(plan Plan) (DiagnosticsResult, error) {
	sizes, err := MeasureSizeMatrix(plan)
	if err != nil {
		return DiagnosticsResult{}, err
	}
	admission := AdmissionBindingValidation(plan)
	result := DiagnosticsResult{SizeMatrix: sizes, AdmissionBinding: admission, AllWireSizesPass: true, AllAdmissionChecksPass: true}
	for _, row := range sizes {
		result.AllWireSizesPass = result.AllWireSizesPass && row.Pass
	}
	for _, row := range admission {
		result.AllAdmissionChecksPass = result.AllAdmissionChecksPass && row.Pass
	}
	return result, nil
}
