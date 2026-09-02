package canonicalv9

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	gatewayv2 "common-action-gateway-v2"
	"common-action-gateway-v2/v7"
	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v8"
	"common-action-gateway-v2/v9ohttp"
	ohttp "github.com/chris-wood/ohttp-go"
)

type RouteSpec struct {
	RouteHandle     string `json:"route_handle"`
	ActionKind      string `json:"action_kind"`
	EffectSemantics string `json:"effect_semantics"`
	Endpoint        string `json:"endpoint"`
	PolicyID        string `json:"policy_id"`
}

type ActionSpec struct {
	OperationID        string `json:"operation_id"`
	ActionKind         string `json:"action_kind"`
	RouteHandle        string `json:"route_handle"`
	EffectSemantics    string `json:"effect_semantics"`
	PolicyID           string `json:"policy_id"`
	ProtectedArguments []byte `json:"protected_arguments"`
}

type Plan struct {
	ProfileID                     string       `json:"profile_id"`
	ProfileClass                  string       `json:"profile_class,omitempty"`
	StateDirectory                string       `json:"state_directory"`
	Rounds                        int          `json:"rounds"`
	AdmissionRounds               int          `json:"admission_rounds"`
	MaximumRealOperations         int          `json:"maximum_real_operations"`
	RoundPeriodMS                 int          `json:"round_period_ms"`
	ProviderCompletionBoundMS     int          `json:"provider_completion_bound_ms"`
	RequestBHTTPBytes             int          `json:"request_bhttp_bytes"`
	ResponseBHTTPBytes            int          `json:"response_bhttp_bytes"`
	RequestFinalBytes             int          `json:"request_final_bytes"`
	ResponseFinalBytes            int          `json:"response_final_bytes"`
	ResponsePreparationLeadMS     int          `json:"response_preparation_lead_ms,omitempty"`
	ResponseInitialReleaseDelayMS int          `json:"response_initial_release_delay_ms,omitempty"`
	ResponsePublicLagMS           int          `json:"response_public_lag_ms,omitempty"`
	ResponsePreparationWorkers    int          `json:"response_preparation_workers,omitempty"`
	SchedulerToleranceMS          int          `json:"scheduler_tolerance_ms,omitempty"`
	PreparationLeadMS             int          `json:"preparation_lead_ms,omitempty"`
	PublicSessionLivenessCapMS    int          `json:"public_session_liveness_cap_ms,omitempty"`
	AdmissionHorizonMS            int          `json:"admission_horizon_ms,omitempty"`
	PIRResolutionPeriodMS         int          `json:"pir_resolution_period_ms,omitempty"`
	PIRPublicEpochMS              int          `json:"pir_public_epoch_ms,omitempty"`
	PIRResolutionOpportunities    int          `json:"pir_resolution_opportunities,omitempty"`
	PIRInitialLeadMS              int          `json:"pir_initial_lead_ms,omitempty"`
	TimingSemanticRevision        string       `json:"timing_semantic_revision,omitempty"`
	FaultDelayResponseSlot        int          `json:"fault_delay_response_slot,omitempty"`
	FaultDelayResponseMS          int          `json:"fault_delay_response_ms,omitempty"`
	FaultSchedulerStallSlot       int          `json:"fault_scheduler_stall_slot,omitempty"`
	FaultSchedulerStallMS         int          `json:"fault_scheduler_stall_ms,omitempty"`
	Routes                        []RouteSpec  `json:"routes"`
	Actions                       []ActionSpec `json:"actions"`
}

type PrivateEvent struct {
	OperationID string `json:"operation_id,omitempty"`
	Stage       string `json:"stage"`
	ActionKind  string `json:"action_kind,omitempty"`
	RouteHandle string `json:"route_handle,omitempty"`
	Status      string `json:"status,omitempty"`
	Round       int    `json:"round,omitempty"`
}

type ClientResult struct {
	OperationID string `json:"operation_id"`
	Status      byte   `json:"status"`
	Payload     []byte `json:"payload"`
	Round       int    `json:"round"`
}

type PublicSetupEvent struct {
	Stage       string `json:"stage"`
	MonotonicNS int64  `json:"monotonic_ns"`
	HTTPVersion string `json:"http_version,omitempty"`
}

type SlotLaunch struct {
	Session               uint32 `json:"session"`
	Slot                  uint32 `json:"slot"`
	DeadlineNS            int64  `json:"deadline_ns"`
	EligibleNS            int64  `json:"eligible_ns,omitempty"`
	PreparationCutoffNS   int64  `json:"preparation_cutoff_ns"`
	PreparationWakeNS     int64  `json:"preparation_wake_ns,omitempty"`
	PreparationLatenessNS int64  `json:"preparation_lateness_ns,omitempty"`
	SleepEntryNS          int64  `json:"sleep_entry_ns,omitempty"`
	SleepWakeNS           int64  `json:"sleep_wake_ns,omitempty"`
	DispatchNS            int64  `json:"scheduler_dispatch_ns,omitempty"`
	HTTPSubmissionNS      int64  `json:"http_submission_ns,omitempty"`
	WakeLatenessNS        int64  `json:"wake_lateness_ns,omitempty"`
	DispatchLatenessNS    int64  `json:"dispatch_lateness_ns,omitempty"`
	SubmitNS              int64  `json:"submit_ns,omitempty"`
	LaunchSlipNS          int64  `json:"launch_slip_ns,omitempty"`
	ToleranceExceeded     bool   `json:"diagnostic_tolerance_exceeded,omitempty"`
	ScheduleMiss          bool   `json:"schedule_miss"`
	Emitted               bool   `json:"emitted"`
}

type SchedulerHostSnapshot struct {
	PID                         int        `json:"pid"`
	TID                         int        `json:"tid"`
	CPU                         int        `json:"cpu"`
	CPUAffinity                 string     `json:"cpu_affinity"`
	GOMAXPROCS                  int        `json:"gomaxprocs"`
	GCCycles                    uint32     `json:"gc_cycles"`
	GCPauseTotalNS              uint64     `json:"gc_pause_total_ns"`
	ProcessCPUTimeTicks         uint64     `json:"process_cpu_time_ticks,omitempty"`
	CPUPressure                 string     `json:"proc_pressure_cpu,omitempty"`
	CgroupNRThrottled           uint64     `json:"cgroup_nr_throttled,omitempty"`
	CgroupThrottledUsec         uint64     `json:"cgroup_throttled_usec,omitempty"`
	LoadAverage                 [3]float64 `json:"load_average"`
	VoluntaryContextSwitches    uint64     `json:"voluntary_context_switches,omitempty"`
	NonvoluntaryContextSwitches uint64     `json:"nonvoluntary_context_switches,omitempty"`
	Unavailable                 []string   `json:"unavailable,omitempty"`
}

type SchedulerIncident struct {
	Slot               uint32                `json:"slot"`
	DeadlineNS         int64                 `json:"deadline_ns"`
	WakeLatenessNS     int64                 `json:"wake_lateness_ns"`
	DispatchLatenessNS int64                 `json:"dispatch_lateness_ns"`
	LaunchSlipNS       int64                 `json:"launch_slip_ns"`
	Before             SchedulerHostSnapshot `json:"before"`
	After              SchedulerHostSnapshot `json:"after"`
}

type SchedulerConfiguration struct {
	Implementation       string `json:"implementation"`
	Clock                string `json:"clock"`
	AbsoluteDeadlines    bool   `json:"absolute_deadlines"`
	OSThreadLocked       bool   `json:"os_thread_locked"`
	PacerTID             int    `json:"pacer_tid"`
	PacerCPU             int    `json:"pacer_cpu"`
	PacerAffinity        string `json:"pacer_affinity"`
	FrameworkProcessCPUs string `json:"framework_process_cpu_set"`
	AffinityRequested    bool   `json:"affinity_requested"`
	AffinitySucceeded    bool   `json:"affinity_succeeded"`
	IsolationVerified    bool   `json:"isolation_verified"`
	AffinityError        string `json:"affinity_error,omitempty"`
	WaitError            string `json:"wait_error,omitempty"`
}

type TransportDiagnostic struct {
	Slot              uint32 `json:"slot"`
	HTTPStatus        int    `json:"http_status,omitempty"`
	ObservedBodyBytes int    `json:"observed_body_bytes,omitempty"`
	ExpectedBodyBytes int    `json:"expected_body_bytes,omitempty"`
	FailureClass      string `json:"failure_class"`
	Error             string `json:"error,omitempty"`
}

type ProviderDiagnostic struct {
	OperationID             string `json:"operation_id"`
	RouteHandle             string `json:"route_handle"`
	Class                   string `json:"class"`
	RequestStartMonotonicNS int64  `json:"request_start_monotonic_ns"`
	HTTPReturnMonotonicNS   int64  `json:"http_return_monotonic_ns,omitempty"`
	ElapsedNS               int64  `json:"elapsed_ns"`
	ContextDeadlineNS       int64  `json:"context_deadline_monotonic_ns"`
	ErrorType               string `json:"error_type,omitempty"`
	Error                   string `json:"error,omitempty"`
	HTTPStatus              int    `json:"http_status,omitempty"`
	BoundedResponseBytes    int    `json:"bounded_response_bytes"`
	JSONDecodeResult        string `json:"json_decode_result"`
	DecodedProviderStatus   string `json:"decoded_provider_status,omitempty"`
}

const (
	TimingIndistinguishabilityProfile = "TIMING_INDISTINGUISHABILITY_PROFILE"
	TimingPublicSessionLivenessCapMS  = 60000

	ProviderOK                      = "PROVIDER_OK"
	ProviderTransportError          = "PROVIDER_TRANSPORT_ERROR"
	ProviderContextDeadlineExceeded = "PROVIDER_CONTEXT_DEADLINE_EXCEEDED"
	ProviderHTTPNon2XX              = "PROVIDER_HTTP_NON_2XX"
	ProviderResponseDecodeError     = "PROVIDER_RESPONSE_DECODE_ERROR"
	ProviderStatusError             = "PROVIDER_STATUS_ERROR"
	ProviderResponseTooLarge        = "PROVIDER_RESPONSE_TOO_LARGE"
	ProviderInternalOtherError      = "PROVIDER_INTERNAL_OTHER_ERROR"
)

type RunResult struct {
	ProfileID                     string                   `json:"profile_id"`
	ProfileClass                  string                   `json:"profile_class,omitempty"`
	Rounds                        int                      `json:"rounds"`
	Admitted                      int                      `json:"admitted"`
	ProviderInvocations           int64                    `json:"provider_invocations"`
	DummyProviderOperations       int64                    `json:"dummy_provider_operations"`
	ProfileOverflowEvents         int                      `json:"profile_overflow_events"`
	Results                       []ClientResult           `json:"results"`
	PrivateEvents                 []PrivateEvent           `json:"private_events"`
	PublicRelayEvents             []v8.RelayPublicEvent    `json:"public_relay_events"`
	AfterCutoffOperations         []string                 `json:"after_cutoff_operations"`
	RequestFinalBytes             int                      `json:"request_final_bytes"`
	ResponseFinalBytes            int                      `json:"response_final_bytes"`
	SessionStatus                 string                   `json:"session_status"`
	PublicSetupEvents             []PublicSetupEvent       `json:"public_setup_events"`
	SlotLaunches                  []SlotLaunch             `json:"slot_launches"`
	ScheduleMisses                int                      `json:"schedule_misses"`
	NominalLateCells              int                      `json:"nominal_late_cells,omitempty"`
	EmittedCells                  int                      `json:"emitted_cells,omitempty"`
	PublicTranscriptComplete      bool                     `json:"public_transcript_complete"`
	InfrastructureLivenessFailure bool                     `json:"infrastructure_liveness_failure"`
	PendingOperationIDs           []string                 `json:"pending_operation_ids"`
	SilentCommittedLosses         int                      `json:"silent_committed_result_losses"`
	ClientRelayHTTPVersion        string                   `json:"client_relay_http_version"`
	RelayGatewayHTTPVersion       string                   `json:"relay_gateway_http_version"`
	OnlineMode                    bool                     `json:"online_mode,omitempty"`
	StartupActionCount            int                      `json:"startup_action_count"`
	AcceptedOperationIDs          []string                 `json:"accepted_operation_ids,omitempty"`
	ResolvedNotAdmittedIDs        []string                 `json:"resolved_not_admitted_ids,omitempty"`
	UnresolvedOperationIDs        []string                 `json:"unresolved_operation_ids,omitempty"`
	FrameworkWaiterIDs            []string                 `json:"framework_waiter_ids,omitempty"`
	TransportDiagnostics          []TransportDiagnostic    `json:"transport_diagnostics,omitempty"`
	ProviderDiagnostics           []ProviderDiagnostic     `json:"provider_diagnostics,omitempty"`
	SchedulerIncidents            []SchedulerIncident      `json:"scheduler_incidents,omitempty"`
	SchedulerConfiguration        SchedulerConfiguration   `json:"scheduler_configuration"`
	GatewayResponseReleases       []gatewayResponseRelease `json:"gateway_response_releases,omitempty"`
	ResponseReleaseOpportunities  int                      `json:"response_release_opportunities,omitempty"`
	ResponseReleaseAttempts       int                      `json:"response_release_attempts,omitempty"`
	SuccessfulResponseWrites      int                      `json:"successful_response_writes,omitempty"`
	RelayApplicationReceivedCells int                      `json:"relay_application_received_cells,omitempty"`
}

type providerRequest struct {
	OperationID string `json:"operation_id"`
	Payload     []byte `json:"payload"`
}

type providerResponse struct {
	Status  string `json:"status"`
	Payload []byte `json:"payload"`
}

type engine struct {
	plan             Plan
	codec            v9ohttp.RFC9292Codec
	client           *v9ohttp.RFC9458Client
	gateway          *v9ohttp.RFC9458Gateway
	routes           map[string]RouteSpec
	journal          *v7.EffectRecoveryJournal
	ready            *v7.DurableReadyQueue
	memory           *v8.MemoryDeliveryQueue
	httpClient       *http.Client
	providerCalls    atomic.Int64
	eventsMu         sync.Mutex
	responseAcks     sync.WaitGroup
	events           []PrivateEvent
	workers          sync.WaitGroup
	slotsMu          sync.Mutex
	seenSlots        map[uint32]bool
	deliveryCutoffs  map[uint32]int64
	deliveryCutoffMu sync.RWMutex
	deliveryMu       sync.Mutex
	providerMu       sync.Mutex
	providerDiags    []ProviderDiagnostic
	started          time.Time
	responseClock    *gatewayResponseVirtualizer
}

func (e *engine) setDeliveryCutoff(slot uint32, cutoffNS int64) {
	e.deliveryCutoffMu.Lock()
	defer e.deliveryCutoffMu.Unlock()
	e.deliveryCutoffs[slot] = cutoffNS
}

func (e *engine) deliveryCutoff(slot uint32) (int64, bool) {
	e.deliveryCutoffMu.RLock()
	defer e.deliveryCutoffMu.RUnlock()
	cutoff, ok := e.deliveryCutoffs[slot]
	return cutoff, ok
}

func effect(value string) (gatewayv2.EffectSemantics, error) {
	switch value {
	case string(gatewayv2.ReadOnly):
		return gatewayv2.ReadOnly, nil
	case string(gatewayv2.IdempotentEffect):
		return gatewayv2.IdempotentEffect, nil
	case string(gatewayv2.NonIdempotentEffect):
		return gatewayv2.NonIdempotentEffect, nil
	default:
		return "", fmt.Errorf("unknown effect semantics %q", value)
	}
}

func actionKind(value string) (v7ohttp.ActionKind, error) {
	switch value {
	case string(v7ohttp.ActionRealTool):
		return v7ohttp.ActionRealTool, nil
	case string(v7ohttp.ActionAgentService):
		return v7ohttp.ActionAgentService, nil
	case string(v7ohttp.ActionExternalHTTP):
		return v7ohttp.ActionExternalHTTP, nil
	default:
		return "", fmt.Errorf("unsupported canonical action kind %q", value)
	}
}

func validateLoopback(endpoint string) error {
	parsed, err := url.Parse(endpoint)
	if err != nil || parsed.Scheme != "http" {
		return errors.New("canonical provider requires local HTTP endpoint")
	}
	host := parsed.Hostname()
	ip := net.ParseIP(host)
	if host != "localhost" && (ip == nil || !ip.IsLoopback()) {
		return errors.New("canonical provider endpoint is not loopback")
	}
	return nil
}

func validatePlan(plan Plan) error {
	if plan.ProfileID == "" || plan.StateDirectory == "" || plan.Rounds < 1 || plan.RoundPeriodMS < 1 {
		return errors.New("incomplete canonical plan")
	}
	if plan.RequestBHTTPBytes < 1 || plan.ResponseBHTTPBytes < 1 ||
		plan.RequestFinalBytes < 1 || plan.ResponseFinalBytes < 1 {
		return errors.New("canonical plan omits fixed wire sizes")
	}
	if len(plan.Actions) > plan.MaximumRealOperations || plan.AdmissionRounds < len(plan.Actions) {
		return errors.New("actions exceed public admission bound")
	}
	if plan.SchedulerToleranceMS < 0 || plan.PreparationLeadMS < 0 || plan.FaultDelayResponseMS < 0 || plan.FaultSchedulerStallMS < 0 {
		return errors.New("negative canonical scheduler configuration")
	}
	if plan.ProfileClass != "" && plan.ProfileClass != TimingIndistinguishabilityProfile {
		return errors.New("unsupported canonical profile class")
	}
	if plan.ProfileClass == TimingIndistinguishabilityProfile && plan.PublicSessionLivenessCapMS != TimingPublicSessionLivenessCapMS {
		return errors.New("timing-indistinguishability profile requires frozen 60000 ms public liveness cap")
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V2-") || strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V3-") {
		expectedRevision := "EFFECTIVE_PUBLIC_CLOCK_V2"
		if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V3-") {
			expectedRevision = "EFFECTIVE_PUBLIC_CLOCK_V3"
		}
		if plan.TimingSemanticRevision != expectedRevision {
			return errors.New("V12 effective-clock profile ID and revision disagree")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 V2 public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 V2 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4" {
			return errors.New("V12 duplex profile ID and revision disagree")
		}
		if plan.ResponsePreparationLeadMS != 5 || plan.ResponsePreparationLeadMS >= plan.RoundPeriodMS {
			return errors.New("V12 duplex response preparation lead changed")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R1-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R1" {
			return errors.New("V12 duplex V4R1 profile ID and revision disagree")
		}
		if plan.ResponsePreparationLeadMS != 25 {
			return errors.New("V12 duplex V4R1 response preparation lead changed")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R1 public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R1 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R2-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R2" {
			return errors.New("V12 duplex V4R2 profile ID and revision disagree")
		}
		if plan.ResponsePreparationLeadMS != 50 {
			return errors.New("V12 duplex V4R2 response preparation lead changed")
		}
		if plan.ResponsePreparationWorkers != 6 {
			return errors.New("V12 duplex V4R2 response preparation worker count changed")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R2 public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R2 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R3-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R3" {
			return errors.New("V12 duplex V4R3 profile ID and revision disagree")
		}
		if plan.ResponsePreparationLeadMS != 50 || plan.ResponsePreparationWorkers != 6 {
			return errors.New("V12 duplex V4R3 response pipeline changed")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R3 public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R3 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R4-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R4" {
			return errors.New("V12 duplex V4R4 profile ID and revision disagree")
		}
		if plan.ResponsePreparationLeadMS != 50 || plan.ResponsePreparationWorkers != 6 {
			return errors.New("V12 duplex V4R4 response pipeline changed")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R4 public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R4 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R5-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R5" {
			return errors.New("V12 duplex V4R5 profile ID and revision disagree")
		}
		if plan.ResponseInitialReleaseDelayMS != 50 || plan.ResponsePreparationLeadMS != 20 || plan.ResponsePreparationWorkers != 6 {
			return errors.New("V12 duplex V4R5 response pipeline changed")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R5 public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R5 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R6-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6" {
			return errors.New("V12 duplex V4R6 profile ID and revision disagree")
		}
		if plan.ResponsePublicLagMS != 30 || plan.ResponsePreparationLeadMS != 20 || plan.ResponsePreparationWorkers != 6 {
			return errors.New("V12 duplex V4R6 response pipeline changed")
		}
		if plan.ResponsePublicLagMS <= plan.ResponsePreparationLeadMS {
			return errors.New("V12 duplex V4R6 public response lag must exceed preparation lead")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R6 public admission horizon disagrees with fixed slot count")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R6 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R7-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R7" {
			return errors.New("V12 duplex V4R7 profile ID and revision disagree")
		}
		if plan.ProviderCompletionBoundMS != 200 {
			return errors.New("V12 duplex V4R7 public provider completion bound changed")
		}
		if plan.ResponsePublicLagMS != 30 || plan.ResponsePreparationLeadMS != 20 || plan.ResponsePreparationWorkers != 6 {
			return errors.New("V12 duplex V4R7 response pipeline changed")
		}
		if plan.ResponsePublicLagMS <= plan.ResponsePreparationLeadMS {
			return errors.New("V12 duplex V4R7 public response lag must exceed preparation lead")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R7 public admission horizon disagrees with fixed slot count")
		}
		completionRounds := (plan.ProviderCompletionBoundMS + plan.RoundPeriodMS - 1) / plan.RoundPeriodMS
		if plan.Rounds != plan.AdmissionRounds+completionRounds+plan.MaximumRealOperations+1 {
			return errors.New("V12 duplex V4R7 fixed transcript capacity disagrees with public B")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R7 public PIR schedule changed")
		}
	}
	if strings.HasPrefix(plan.ProfileID, "V12-TIMING-INDIST-V4R8-") {
		if plan.TimingSemanticRevision != "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8" {
			return errors.New("V12 duplex V4R8 profile ID and revision disagree")
		}
		if plan.ProviderCompletionBoundMS != 200 {
			return errors.New("V12 duplex V4R8 public provider completion bound changed")
		}
		if plan.ResponsePublicLagMS != 30 || plan.ResponsePreparationLeadMS != 20 || plan.ResponsePreparationWorkers != 6 {
			return errors.New("V12 duplex V4R8 response pipeline changed")
		}
		if plan.ResponsePublicLagMS <= plan.ResponsePreparationLeadMS {
			return errors.New("V12 duplex V4R8 public response lag must exceed preparation lead")
		}
		if plan.AdmissionHorizonMS != plan.AdmissionRounds*plan.RoundPeriodMS {
			return errors.New("V12 duplex V4R8 public admission horizon disagrees with fixed slot count")
		}
		completionRounds := (plan.ProviderCompletionBoundMS + plan.RoundPeriodMS - 1) / plan.RoundPeriodMS
		if plan.Rounds != plan.AdmissionRounds+completionRounds+plan.MaximumRealOperations+1 {
			return errors.New("V12 duplex V4R8 fixed transcript capacity disagrees with public B")
		}
		if plan.PIRResolutionPeriodMS != 60 || plan.PIRPublicEpochMS != 6000 ||
			plan.PIRResolutionOpportunities != 100 || plan.PIRInitialLeadMS != 25 {
			return errors.New("V12 duplex V4R8 public PIR schedule changed")
		}
	}
	for _, slot := range []int{plan.FaultDelayResponseSlot, plan.FaultSchedulerStallSlot} {
		if slot < 0 || slot > plan.Rounds {
			return errors.New("canonical fault slot is outside public rounds")
		}
	}
	seenRoutes := make(map[string]bool)
	for _, route := range plan.Routes {
		if route.RouteHandle == "" || route.PolicyID == "" || seenRoutes[route.RouteHandle] {
			return errors.New("invalid or duplicate private route handle")
		}
		seenRoutes[route.RouteHandle] = true
		if _, err := actionKind(route.ActionKind); err != nil {
			return err
		}
		if _, err := effect(route.EffectSemantics); err != nil {
			return err
		}
		if err := validateLoopback(route.Endpoint); err != nil {
			return err
		}
	}
	for _, action := range plan.Actions {
		if action.OperationID == "" || !seenRoutes[action.RouteHandle] {
			return errors.New("action uses absent private route")
		}
	}
	return nil
}

func (e *engine) record(event PrivateEvent) {
	e.eventsMu.Lock()
	defer e.eventsMu.Unlock()
	e.events = append(e.events, event)
}

func resultRecord(operationID string, status byte, payload []byte) gatewayv2.ResultRecord {
	if len(payload) > gatewayv2.ResultPayloadBytes {
		payload = payload[:gatewayv2.ResultPayloadBytes]
	}
	result := gatewayv2.ResultRecord{Status: status, OperationID: gatewayv2.OperationID(operationID), PayloadLen: uint16(len(payload))}
	copy(result.Payload[:], payload)
	return result
}

type providerAttempt struct {
	status     byte
	payload    []byte
	diagnostic ProviderDiagnostic
}

func (e *engine) callProvider(route RouteSpec, operationID string, protectedArgs []byte) providerAttempt {
	start := time.Now()
	startNS := start.Sub(e.started).Nanoseconds()
	bound := time.Duration(e.plan.ProviderCompletionBoundMS) * time.Millisecond
	diagnostic := ProviderDiagnostic{
		OperationID:             operationID,
		RouteHandle:             route.RouteHandle,
		Class:                   ProviderInternalOtherError,
		RequestStartMonotonicNS: startNS,
		ContextDeadlineNS:       startNS + bound.Nanoseconds(),
		JSONDecodeResult:        "NOT_ATTEMPTED",
	}
	finish := func(status byte) providerAttempt {
		diagnostic.ElapsedNS = time.Since(start).Nanoseconds()
		return providerAttempt{status: status, diagnostic: diagnostic}
	}
	body, err := json.Marshal(providerRequest{OperationID: operationID, Payload: protectedArgs})
	if err != nil {
		diagnostic.ErrorType = fmt.Sprintf("%T", err)
		diagnostic.Error = err.Error()
		return finish(gatewayv2.StatusError)
	}
	request, err := http.NewRequestWithContext(context.Background(), http.MethodPost, route.Endpoint, bytes.NewReader(body))
	if err != nil {
		diagnostic.ErrorType = fmt.Sprintf("%T", err)
		diagnostic.Error = err.Error()
		return finish(gatewayv2.StatusError)
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := e.httpClient.Do(request)
	diagnostic.HTTPReturnMonotonicNS = time.Since(e.started).Nanoseconds()
	if err != nil {
		diagnostic.ErrorType = fmt.Sprintf("%T", err)
		diagnostic.Error = err.Error()
		if errors.Is(err, context.DeadlineExceeded) {
			diagnostic.Class = ProviderContextDeadlineExceeded
			return finish(gatewayv2.StatusTimeout)
		} else {
			diagnostic.Class = ProviderTransportError
		}
		return finish(gatewayv2.StatusError)
	}
	defer response.Body.Close()
	diagnostic.HTTPStatus = response.StatusCode
	const responseLimit = int64(gatewayv2.ResultPayloadBytes + 1024)
	raw, readErr := io.ReadAll(io.LimitReader(response.Body, responseLimit+1))
	diagnostic.BoundedResponseBytes = len(raw)
	if readErr != nil {
		diagnostic.ErrorType = fmt.Sprintf("%T", readErr)
		diagnostic.Error = readErr.Error()
		if errors.Is(readErr, context.DeadlineExceeded) {
			diagnostic.Class = ProviderContextDeadlineExceeded
			return finish(gatewayv2.StatusTimeout)
		}
		diagnostic.Class = ProviderTransportError
		return finish(gatewayv2.StatusError)
	}
	if int64(len(raw)) > responseLimit {
		diagnostic.Class = ProviderResponseTooLarge
		diagnostic.JSONDecodeResult = "SKIPPED_RESPONSE_TOO_LARGE"
		return finish(gatewayv2.StatusError)
	}
	if response.StatusCode/100 != 2 {
		diagnostic.Class = ProviderHTTPNon2XX
		diagnostic.JSONDecodeResult = "SKIPPED_HTTP_NON_2XX"
		return finish(gatewayv2.StatusError)
	}
	var decoded providerResponse
	if err := json.NewDecoder(bytes.NewReader(raw)).Decode(&decoded); err != nil {
		diagnostic.Class = ProviderResponseDecodeError
		diagnostic.ErrorType = fmt.Sprintf("%T", err)
		diagnostic.Error = err.Error()
		diagnostic.JSONDecodeResult = "ERROR"
		return finish(gatewayv2.StatusError)
	}
	diagnostic.JSONDecodeResult = "OK"
	diagnostic.DecodedProviderStatus = decoded.Status
	if decoded.Status != "OK" {
		diagnostic.Class = ProviderStatusError
		return finish(gatewayv2.StatusError)
	}
	diagnostic.Class = ProviderOK
	diagnostic.ElapsedNS = time.Since(start).Nanoseconds()
	return providerAttempt{status: gatewayv2.StatusOK, payload: decoded.Payload, diagnostic: diagnostic}
}

func (e *engine) recordProviderDiagnostic(diagnostic ProviderDiagnostic) {
	e.providerMu.Lock()
	defer e.providerMu.Unlock()
	e.providerDiags = append(e.providerDiags, diagnostic)
}

func (e *engine) providerDiagnostics() []ProviderDiagnostic {
	e.providerMu.Lock()
	defer e.providerMu.Unlock()
	return append([]ProviderDiagnostic(nil), e.providerDiags...)
}

func (e *engine) execute(route RouteSpec, action v7ohttp.PrivateActionMessage, currentRound uint32) {
	defer e.workers.Done()
	operationID := string(action.OperationID)
	e.providerCalls.Add(1)
	e.record(PrivateEvent{OperationID: operationID, Stage: "PROVIDER_CALL_BEGIN", ActionKind: string(action.Kind), RouteHandle: route.RouteHandle, Round: int(currentRound)})
	attempt := e.callProvider(route, operationID, action.ProtectedArgs)
	e.recordProviderDiagnostic(attempt.diagnostic)
	result := resultRecord(operationID, attempt.status, attempt.payload)
	if err := e.journal.Commit(operationID, result); err != nil {
		e.record(PrivateEvent{OperationID: operationID, Stage: "RESULT_COMMIT_FAILED", Status: err.Error()})
		return
	}
	e.record(PrivateEvent{OperationID: operationID, Stage: "RESULT_COMMITTED", Status: fmt.Sprintf("%d", attempt.status)})
	if _, err := e.ready.Enqueue(result, time.Now().UnixNano()); err != nil {
		e.record(PrivateEvent{OperationID: operationID, Stage: "READY_PUBLICATION_FAILED", Status: err.Error()})
		return
	}
	e.record(PrivateEvent{OperationID: operationID, Stage: "READY_PUBLISHED"})
}

func (e *engine) accept(action v7ohttp.PrivateActionMessage, currentRound uint32) error {
	if action.Kind == v7ohttp.ActionNoop {
		return nil
	}
	route, ok := e.routes[string(action.RouteHandle)]
	if !ok {
		return errors.New("private route handle not present in trusted Gateway map")
	}
	if route.ActionKind != string(action.Kind) {
		return errors.New("private action kind does not match trusted route")
	}
	var authorization struct {
		EffectSemantics string `json:"effect_semantics"`
		PolicyID        string `json:"policy_id"`
	}
	if json.Unmarshal(action.Authorization, &authorization) != nil ||
		authorization.EffectSemantics != route.EffectSemantics || authorization.PolicyID != route.PolicyID {
		return errors.New("private authorization metadata does not match trusted route")
	}
	semantics, _ := effect(route.EffectSemantics)
	operationID := string(action.OperationID)
	decision, committed, err := e.journal.Begin(operationID, semantics)
	if err != nil {
		return err
	}
	e.record(PrivateEvent{OperationID: operationID, Stage: "ACCEPTED", ActionKind: string(action.Kind), RouteHandle: route.RouteHandle, Round: int(currentRound)})
	switch decision {
	case v7.RecoveryReturnResult:
		if _, err := e.ready.Enqueue(committed, time.Now().UnixNano()); err != nil {
			return err
		}
		e.record(PrivateEvent{OperationID: operationID, Stage: "RECOVERY_COMMITTED_RESULT_REPUBLISHED"})
		return nil
	case v7.RecoveryOutcomeUnknown:
		ambiguous := resultRecord(operationID, gatewayv2.StatusAmbiguous, nil)
		if err := e.journal.Commit(operationID, ambiguous); err != nil {
			return err
		}
		if _, err := e.ready.Enqueue(ambiguous, time.Now().UnixNano()); err != nil {
			return err
		}
		e.record(PrivateEvent{OperationID: operationID, Stage: "RECOVERY_EFFECT_OUTCOME_UNKNOWN"})
		return nil
	case v7.RecoveryExecute:
		// Begin atomically persists a fresh operation in PROVIDER_STARTED. On
		// restart, READ_ONLY or explicitly idempotent work is replay-authorized;
		// non-idempotent ambiguity is handled above.
		e.record(PrivateEvent{OperationID: operationID, Stage: "PROVIDER_STARTED_DURABLE"})
	default:
		return errors.New("unknown canonical recovery decision")
	}
	e.workers.Add(1)
	go e.execute(route, action, currentRound)
	return nil
}

func privateResponse(record *gatewayv2.ResultRecord) v7ohttp.PrivateResponse {
	if record == nil {
		return v7ohttp.PrivateResponse{Status: v9ohttp.StatusWait}
	}
	status := v9ohttp.StatusError
	switch record.Status {
	case gatewayv2.StatusOK:
		status = v9ohttp.StatusResult
	case gatewayv2.StatusTimeout:
		status = v9ohttp.StatusTimeout
	case gatewayv2.StatusAmbiguous:
		status = v9ohttp.StatusEffectOutcomeUnknown
	}
	return v7ohttp.PrivateResponse{Status: status, OperationID: gatewayv2.OperationIDString(record.OperationID), Payload: append([]byte(nil), record.Payload[:record.PayloadLen]...)}
}

func (e *engine) claimPublicSlot(request *http.Request) (v7ohttp.SlotID, error) {
	sessionValue, err := strconv.ParseUint(request.Header.Get("X-AgentTool-Public-Session"), 10, 32)
	if err != nil || sessionValue != 1 {
		return v7ohttp.SlotID{}, errors.New("invalid public session")
	}
	slotValue, err := strconv.ParseUint(request.Header.Get("X-AgentTool-Public-Slot"), 10, 32)
	if err != nil || slotValue == 0 || slotValue > uint64(e.plan.Rounds) {
		return v7ohttp.SlotID{}, errors.New("invalid public slot")
	}
	slot := uint32(slotValue)
	e.slotsMu.Lock()
	defer e.slotsMu.Unlock()
	if e.seenSlots[slot] {
		return v7ohttp.SlotID{}, errors.New("duplicate public slot")
	}
	e.seenSlots[slot] = true
	return v7ohttp.SlotID{Session: 1, Slot: slot}, nil
}

func (e *engine) commitGatewayResponse(slot v7ohttp.SlotID, responseContext v7ohttp.ServerContext,
	cutoffNS int64) (func() (v8.PreparedSlot, error), error) {
	e.deliveryMu.Lock()
	defer e.deliveryMu.Unlock()
	var selected *gatewayv2.ResultRecord
	var err error
	if cutoffNS > 0 {
		selected, err = e.ready.ReserveEligibleBefore(1, slot.Slot, cutoffNS)
	} else {
		selected, err = e.ready.ReserveEligible(1, slot.Slot)
	}
	if err != nil {
		return nil, err
	}
	if selected != nil {
		if err := e.memory.PublishDurable(*selected); err != nil {
			return nil, err
		}
	}
	committedResult := privateResponse(e.memory.SnapshotEligible(1))
	operationID := ""
	if committedResult.OperationID != "" {
		operationID = committedResult.OperationID
	}
	return func() (v8.PreparedSlot, error) {
		if e.plan.FaultDelayResponseSlot == int(slot.Slot) && e.plan.FaultDelayResponseMS > 0 {
			// Development-only, secret-independent fault injection for the fixed
			// public response preparation path.
			time.Sleep(time.Duration(e.plan.FaultDelayResponseMS) * time.Millisecond)
		}
		bhttpResponse, err := e.codec.EncodeKnownLengthResponseBound(
			committedResult, e.plan.ResponseBHTTPBytes, slot,
		)
		if err != nil {
			return v8.PreparedSlot{}, err
		}
		wire, err := e.gateway.EncapsulateResponse(responseContext, bhttpResponse)
		if err != nil || len(wire) != e.plan.ResponseFinalBytes {
			return v8.PreparedSlot{}, errors.New("OHTTP response failed")
		}
		ack := make(chan string, 1)
		prepared := v8.PreparedSlot{Frame: wire, OperationID: operationID, Ack: ack}
		if prepared.OperationID != "" {
			e.responseAcks.Add(1)
			go func() {
				defer e.responseAcks.Done()
				<-prepared.Ack
				_ = e.ready.MarkDelivered(prepared.OperationID)
				_ = e.journal.MarkResultDelivered(prepared.OperationID)
				e.record(PrivateEvent{OperationID: prepared.OperationID, Stage: "GATEWAY_DELIVERY_ACK_DURABLE", Round: int(slot.Slot)})
			}()
		}
		return prepared, nil
	}, nil
}

func (e *engine) prepareGatewayResponse(slot v7ohttp.SlotID, responseContext v7ohttp.ServerContext,
	cutoffNS int64) (v8.PreparedSlot, error) {
	prepare, err := e.commitGatewayResponse(slot, responseContext, cutoffNS)
	if err != nil {
		return v8.PreparedSlot{}, err
	}
	return prepare()
}

func (e *engine) gatewayHandler(writer http.ResponseWriter, request *http.Request) {
	requestArrival := time.Now()
	slot, err := e.claimPublicSlot(request)
	if err != nil {
		http.Error(writer, "public slot rejected", http.StatusBadRequest)
		return
	}
	currentRound := slot.Slot
	body, err := io.ReadAll(io.LimitReader(request.Body, int64(e.plan.RequestFinalBytes+1)))
	if err != nil || len(body) != e.plan.RequestFinalBytes {
		http.Error(writer, "invalid OHTTP request", http.StatusBadRequest)
		return
	}
	plaintext, responseContext, err := e.gateway.DecapsulateRequest(slot, body)
	if err != nil {
		http.Error(writer, "OHTTP decapsulation failed", http.StatusBadRequest)
		return
	}
	if responseContext.Slot() != slot {
		http.Error(writer, "OHTTP server context slot mismatch", http.StatusInternalServerError)
		return
	}
	_, action, innerSlot, err := e.codec.DecodeKnownLengthRequestBound(plaintext)
	if err != nil || innerSlot != slot || e.accept(action, currentRound) != nil {
		http.Error(writer, "private action rejected", http.StatusBadRequest)
		return
	}
	writer.Header().Set("Content-Type", v8.OHTTPResponseContentType)
	writer.Header().Set("Content-Length", fmt.Sprintf("%d", e.plan.ResponseFinalBytes))
	if e.responseClock != nil {
		err := e.responseClock.release(currentRound, requestArrival, func(cutoff time.Time) (func() (v8.PreparedSlot, error), error) {
			return e.commitGatewayResponse(slot, responseContext, cutoff.UnixNano())
		}, writer)
		if err != nil {
			e.record(PrivateEvent{Stage: "DUPLEX_RESPONSE_RELEASE_FAILED", Status: err.Error(), Round: int(currentRound)})
		}
		return
	}
	cutoffNS := int64(0)
	if e.plan.ProfileClass == TimingIndistinguishabilityProfile {
		var ok bool
		cutoffNS, ok = e.deliveryCutoff(currentRound)
		if !ok {
			http.Error(writer, "effective result cutoff unavailable", http.StatusInternalServerError)
			return
		}
	}
	prepared, err := e.prepareGatewayResponse(slot, responseContext, cutoffNS)
	if err != nil {
		http.Error(writer, "response preparation failed", http.StatusInternalServerError)
		return
	}
	writer.WriteHeader(http.StatusOK)
	if err := prepared.Send(writer); err != nil {
		return
	}
}

func newEngine(plan Plan) (*engine, error) {
	if err := validatePlan(plan); err != nil {
		return nil, err
	}
	private, err := ohttp.NewConfig(7, 0x0020, 0x0001, 0x0001)
	if err != nil {
		return nil, err
	}
	suite := v9ohttp.PublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001, ConfigurationEpoch: 3, AuthenticatedSource: "V9_CANONICAL_LOCAL"}
	client, err := v9ohttp.NewRFC9458Client(private.Config(), suite)
	if err != nil {
		return nil, err
	}
	gateway, err := v9ohttp.NewRFC9458Gateway(private, suite)
	if err != nil {
		return nil, err
	}
	journal, err := v7.OpenEffectRecoveryJournal(filepath.Join(plan.StateDirectory, "effect_recovery.json"))
	if err != nil {
		return nil, err
	}
	ready, err := v7.OpenDurableReadyQueue(filepath.Join(plan.StateDirectory, "ready_results.json"), plan.MaximumRealOperations+1)
	if err != nil {
		return nil, err
	}
	memory, err := v8.NewMemoryDeliveryQueue(plan.MaximumRealOperations + 1)
	if err != nil {
		return nil, err
	}
	routes := make(map[string]RouteSpec)
	for _, route := range plan.Routes {
		routes[route.RouteHandle] = route
	}
	return &engine{plan: plan, codec: v9ohttp.RFC9292Codec{}, client: client, gateway: gateway,
		routes: routes, journal: journal, ready: ready, memory: memory,
		httpClient: &http.Client{Timeout: time.Duration(plan.ProviderCompletionBoundMS) * time.Millisecond},
		seenSlots:  make(map[uint32]bool, plan.Rounds), deliveryCutoffs: make(map[uint32]int64, plan.Rounds),
		started: time.Now()}, nil
}

func bindAdmission(plan Plan) error {
	profile, admission := canonicalProfiles(plan)
	return v8.BindAdmission(profile, admission)
}

func Run(plan Plan) (RunResult, error) {
	if err := bindAdmission(plan); err != nil {
		return RunResult{}, err
	}
	if err := os.MkdirAll(plan.StateDirectory, 0o700); err != nil {
		return RunResult{}, err
	}
	engine, err := newEngine(plan)
	if err != nil {
		return RunResult{}, err
	}
	processClock := time.Now()
	monotonicNS := func() int64 { return time.Since(processClock).Nanoseconds() }
	setupEvents := []PublicSetupEvent{{Stage: "GATEWAY_INSTANTIATED", MonotonicNS: monotonicNS()}}
	gatewayMux := http.NewServeMux()
	gatewayMux.HandleFunc("/preconnect", func(writer http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet || request.ProtoMajor != 2 {
			http.Error(writer, "canonical Gateway HTTP/2 preconnect rejected", http.StatusHTTPVersionNotSupported)
			return
		}
		writer.WriteHeader(http.StatusNoContent)
	})
	gatewayMux.HandleFunc("/", engine.gatewayHandler)
	gatewayServer := httptest.NewUnstartedServer(gatewayMux)
	gatewayServer.EnableHTTP2 = true
	gatewayServer.StartTLS()
	defer gatewayServer.Close()
	setupEvents = append(setupEvents, PublicSetupEvent{Stage: "GATEWAY_READY", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"})
	relayProfile := v8.ScheduleProfile{ProfileID: plan.ProfileID, Sessions: 1, SlotsPerSession: plan.Rounds,
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes,
		RequestIntervalNS:         int64(time.Duration(plan.RoundPeriodMS) * time.Millisecond),
		ResponseSlotIntervalNS:    int64(time.Duration(plan.RoundPeriodMS) * time.Millisecond),
		PublicLifetimeNS:          int64(time.Duration(plan.Rounds*plan.RoundPeriodMS) * time.Millisecond),
		MaximumAdmittedOperations: plan.MaximumRealOperations, TerminalSlots: 1,
		ProviderCompletionBoundNS: int64(time.Duration(plan.ProviderCompletionBoundMS) * time.Millisecond),
		RelayEndpoint:             "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY", ConnectionPolicy: "KEEP_ALIVE",
		OHTTPSuite: v8.OHTTPPublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 0x0001, AEADID: 0x0001, ConfigEpoch: 3}}
	relay, err := v8.NewFreshRequestRelayWithClient(relayProfile, gatewayServer.URL, gatewayServer.Client(), true)
	if err != nil {
		return RunResult{}, err
	}
	relayServer := httptest.NewUnstartedServer(relay)
	relayServer.EnableHTTP2 = true
	relayServer.StartTLS()
	defer relayServer.Close()
	setupEvents = append(setupEvents, PublicSetupEvent{Stage: "RELAY_READY", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"})
	clientHTTP := relayServer.Client()
	preconnectRequest, _ := http.NewRequest(http.MethodGet, relayServer.URL+"/preconnect", nil)
	preconnectResponse, err := clientHTTP.Do(preconnectRequest)
	if err != nil {
		return RunResult{}, fmt.Errorf("PUBLIC_PRECONNECT failed: %w", err)
	}
	preconnectProto := preconnectResponse.Proto
	preconnectResponse.Body.Close()
	complete, clientH2, gatewayH2 := relay.PreconnectStatus()
	if preconnectResponse.StatusCode != http.StatusNoContent || preconnectProto != "HTTP/2.0" || !complete || !clientH2 || !gatewayH2 {
		return RunResult{}, errors.New("PUBLIC_PRECONNECT did not establish both HTTP/2 hops")
	}
	setupEvents = append(setupEvents,
		PublicSetupEvent{Stage: "CLIENT_RELAY_HTTP2_ESTABLISHED", MonotonicNS: monotonicNS(), HTTPVersion: preconnectProto},
		PublicSetupEvent{Stage: "RELAY_GATEWAY_HTTP2_ESTABLISHED", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"},
		PublicSetupEvent{Stage: "PUBLIC_SETUP_COMPLETE", MonotonicNS: monotonicNS(), HTTPVersion: "HTTP/2.0"},
	)

	type preparedRequest struct {
		slot    v7ohttp.SlotID
		wire    []byte
		context v7ohttp.ClientContext
	}
	prepared := make([]preparedRequest, 0, plan.Rounds)
	// Private action material is first inspected only after public transport
	// setup completed.  Every slot is fully encapsulated before T0.
	for round := 1; round <= plan.Rounds; round++ {
		message := v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionNoop, OperationID: []byte(fmt.Sprintf("noop-%06d", round))}
		if round <= len(plan.Actions) {
			action := plan.Actions[round-1]
			kind, _ := actionKind(action.ActionKind)
			authorization, _ := json.Marshal(map[string]string{"effect_semantics": action.EffectSemantics, "policy_id": action.PolicyID})
			message = v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: kind,
				RouteHandle: []byte(action.RouteHandle), OperationID: []byte(action.OperationID),
				ProtectedArgs: action.ProtectedArguments, Authorization: authorization}
		}
		slot := v7ohttp.SlotID{Session: 1, Slot: uint32(round)}
		bhttpRequest, err := engine.codec.EncodeKnownLengthRequestBound(v7ohttp.InnerSemanticTarget, message, plan.RequestBHTTPBytes, slot)
		if err != nil {
			return RunResult{}, err
		}
		wire, responseContext, err := engine.client.EncapsulateRequest(slot, bhttpRequest)
		if err != nil || len(wire) != plan.RequestFinalBytes {
			return RunResult{}, errors.New("canonical request final size mismatch")
		}
		if responseContext.Slot() != slot {
			return RunResult{}, errors.New("OHTTP client context slot mismatch")
		}
		prepared = append(prepared, preparedRequest{slot: slot, wire: wire, context: responseContext})
	}
	setupEvents = append(setupEvents, PublicSetupEvent{Stage: "PREPARED_REQUEST_TABLE_COMPLETE", MonotonicNS: monotonicNS()})

	type slotResponse struct {
		slot        v7ohttp.SlotID
		wire        []byte
		httpVersion string
		err         error
		diagnostic  *TransportDiagnostic
	}
	responses := make(chan slotResponse, plan.Rounds)
	period := time.Duration(plan.RoundPeriodMS) * time.Millisecond
	tolerance := time.Duration(plan.SchedulerToleranceMS) * time.Millisecond
	if tolerance <= 0 {
		// Backward-compatible development default. V11.1 profiles set this
		// explicitly before stress testing.
		tolerance = 2 * period
	}
	t0 := time.Now().Add(period)
	setupEvents = append(setupEvents, PublicSetupEvent{Stage: "T0_ASSIGNED", MonotonicNS: monotonicNS()})
	launches := make([]SlotLaunch, 0, plan.Rounds)
	submitted := 0
	for index, item := range prepared {
		deadline := t0.Add(time.Duration(index) * period)
		if remaining := time.Until(deadline); remaining > 0 {
			time.Sleep(remaining)
		}
		if plan.FaultSchedulerStallSlot == index+1 && plan.FaultSchedulerStallMS > 0 {
			time.Sleep(time.Duration(plan.FaultSchedulerStallMS) * time.Millisecond)
		}
		submitTime := time.Now()
		slip := submitTime.Sub(deadline)
		launch := SlotLaunch{Session: 1, Slot: uint32(index + 1), DeadlineNS: deadline.Sub(processClock).Nanoseconds(),
			LaunchSlipNS: slip.Nanoseconds()}
		// A slot that has crossed the next public deadline is expired even if a
		// looser diagnostic tolerance was configured.  Submitting it would
		// recreate the historical catch-up burst.
		launch.ToleranceExceeded = slip > tolerance
		if slip >= period {
			launch.ScheduleMiss = true
			launches = append(launches, launch)
			continue
		}
		launch.SubmitNS = submitTime.Sub(processClock).Nanoseconds()
		launches = append(launches, launch)
		submitted++
		go func(value preparedRequest) {
			request, requestErr := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(value.wire))
			if requestErr != nil {
				responses <- slotResponse{slot: value.slot, err: requestErr}
				return
			}
			request.Header.Set("Content-Type", v8.OHTTPRequestContentType)
			request.Header.Set("X-AgentTool-Public-Session", "1")
			request.Header.Set("X-AgentTool-Public-Slot", strconv.FormatUint(uint64(value.slot.Slot), 10))
			request.ContentLength = int64(len(value.wire))
			response, requestErr := clientHTTP.Do(request)
			if requestErr != nil {
				responses <- slotResponse{slot: value.slot, err: requestErr}
				return
			}
			responseWire, readErr := io.ReadAll(io.LimitReader(response.Body, int64(plan.ResponseFinalBytes+1)))
			response.Body.Close()
			if readErr != nil {
				responses <- slotResponse{slot: value.slot, err: readErr}
				return
			}
			if response.StatusCode != http.StatusOK || len(responseWire) != plan.ResponseFinalBytes {
				failureClass := "RESPONSE_BODY_LENGTH_MISMATCH"
				if response.StatusCode != http.StatusOK {
					failureClass = "GATEWAY_NON_200"
				}
				diagnostic := &TransportDiagnostic{Slot: value.slot.Slot, HTTPStatus: response.StatusCode,
					ObservedBodyBytes: len(responseWire), ExpectedBodyBytes: plan.ResponseFinalBytes,
					FailureClass: failureClass}
				responses <- slotResponse{slot: value.slot,
					err: fmt.Errorf("canonical response validation failed: slot=%d http_status=%d observed_body_bytes=%d expected_body_bytes=%d class=%s",
						value.slot.Slot, response.StatusCode, len(responseWire), plan.ResponseFinalBytes, failureClass),
					diagnostic: diagnostic}
				return
			}
			responses <- slotResponse{slot: value.slot, wire: responseWire, httpVersion: response.Proto}
		}(item)
	}

	results := make([]ClientResult, 0, len(plan.Actions))
	transportFailure := false
	transportDiagnostics := make([]TransportDiagnostic, 0)
	for count := 0; count < submitted; count++ {
		response := <-responses
		if response.err != nil || response.httpVersion != "HTTP/2.0" {
			transportFailure = true
			if response.diagnostic != nil {
				transportDiagnostics = append(transportDiagnostics, *response.diagnostic)
			} else if response.err != nil {
				transportDiagnostics = append(transportDiagnostics, TransportDiagnostic{Slot: response.slot.Slot,
					FailureClass: "TRANSPORT_ERROR", Error: response.err.Error()})
			}
			continue
		}
		context := prepared[int(response.slot.Slot)-1].context
		opened, err := engine.client.DecapsulateResponse(context, response.wire)
		if err != nil {
			transportFailure = true
			continue
		}
		decoded, innerSlot, err := engine.codec.DecodeKnownLengthResponseBound(opened)
		if err != nil || innerSlot != response.slot {
			transportFailure = true
			continue
		}
		if decoded.Status != v9ohttp.StatusWait {
			results = append(results, ClientResult{OperationID: decoded.OperationID, Status: decoded.Status,
				Payload: decoded.Payload, Round: int(response.slot.Slot)})
			engine.record(PrivateEvent{OperationID: decoded.OperationID, Stage: "CLIENT_BHTTP_DECODED",
				Status: fmt.Sprintf("%d", decoded.Status), Round: int(response.slot.Slot)})
		}
	}
	engine.workers.Wait()
	engine.responseAcks.Wait()
	sort.Slice(results, func(i, j int) bool { return results[i].Round < results[j].Round })
	delivered := make(map[string]bool, len(results))
	for _, result := range results {
		delivered[result.OperationID] = true
	}
	pending := make([]string, 0)
	for _, action := range plan.Actions {
		if !delivered[action.OperationID] {
			pending = append(pending, action.OperationID)
		}
	}
	scheduleMisses := 0
	for _, launch := range launches {
		if launch.ScheduleMiss {
			scheduleMisses++
		}
	}
	status := "COMPLETE"
	if scheduleMisses > 0 {
		status = "SESSION_SCHEDULE_FAILURE"
	} else if transportFailure || submitted != plan.Rounds {
		status = "SESSION_TRANSPORT_FAILURE"
	} else if len(pending) > 0 {
		status = "SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT"
	}
	return RunResult{ProfileID: plan.ProfileID, Rounds: plan.Rounds, Admitted: len(plan.Actions),
		ProviderInvocations: engine.providerCalls.Load(), DummyProviderOperations: 0,
		Results: results, PrivateEvents: append([]PrivateEvent(nil), engine.events...),
		PublicRelayEvents: relay.Events(), AfterCutoffOperations: []string{"wait", "PreparedSlot.Send", "one fixed-size writer.Write", "byte-count validation", "non-blocking in-memory acknowledgement"},
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes,
		SessionStatus: status, PublicSetupEvents: setupEvents, SlotLaunches: launches,
		ScheduleMisses: scheduleMisses, PendingOperationIDs: pending, SilentCommittedLosses: 0,
		ClientRelayHTTPVersion: preconnectProto, RelayGatewayHTTPVersion: "HTTP/2.0",
		TransportDiagnostics: transportDiagnostics, ProviderDiagnostics: engine.providerDiagnostics()}, nil
}
