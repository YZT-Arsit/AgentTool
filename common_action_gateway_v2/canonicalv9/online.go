package canonicalv9

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"sort"
	"strconv"
	"sync"
	"time"

	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v8"
	"common-action-gateway-v2/v9ohttp"
)

// OnlineControlMessage is the trusted local IPC protocol. It is deliberately
// separate from the Relay-visible transport.
type OnlineControlMessage struct {
	Type   string      `json:"type"`
	Action *ActionSpec `json:"action,omitempty"`
}

type OnlineControlEvent struct {
	Type        string        `json:"type"`
	OperationID string        `json:"operation_id,omitempty"`
	Reason      string        `json:"reason,omitempty"`
	Round       int           `json:"round,omitempty"`
	Result      *ClientResult `json:"result,omitempty"`
}

type onlineEmitter struct {
	mu      sync.Mutex
	encoder *json.Encoder
}

func exactRelayPublicSlotInventory(events []v8.RelayPublicEvent, rounds int) bool {
	if len(events) != rounds || rounds < 1 {
		return false
	}
	seen := make([]bool, rounds)
	for _, event := range events {
		if event.Session != 1 || event.Round < 1 || int(event.Round) > rounds {
			return false
		}
		index := int(event.Round) - 1
		if seen[index] {
			return false
		}
		seen[index] = true
	}
	for _, present := range seen {
		if !present {
			return false
		}
	}
	return true
}

func (e *onlineEmitter) emit(value OnlineControlEvent) {
	e.mu.Lock()
	defer e.mu.Unlock()
	_ = e.encoder.Encode(value)
}

type onlinePreparedRequest struct {
	slot        v7ohttp.SlotID
	wire        []byte
	context     v7ohttp.ClientContext
	operationID string
	real        bool
}

type onlineSlotPhase uint8

const (
	onlineSlotFuture onlineSlotPhase = iota
	onlineSlotEffectiveCutoffFixed
	onlineSlotLogicallyCommitted
	onlineSlotPhysicallyEmitted
)

type onlineSlotState struct {
	mu              sync.Mutex
	nominalDeadline time.Time
	effective       time.Time
	cutoff          time.Time
	phase           onlineSlotPhase
	cutoffReady     chan struct{}
	noop            onlinePreparedRequest
	real            *onlinePreparedRequest
	realCommittedAt time.Time
}

func newOnlineSlotState(deadline time.Time, noop onlinePreparedRequest) *onlineSlotState {
	return &onlineSlotState{
		nominalDeadline: deadline,
		phase:           onlineSlotFuture,
		cutoffReady:     make(chan struct{}),
		noop:            noop,
	}
}

func effectivePublicEligibility(nominal, previousDispatch time.Time, period time.Duration) time.Time {
	if !previousDispatch.IsZero() && previousDispatch.Add(period).After(nominal) {
		return previousDispatch.Add(period)
	}
	return nominal
}

func (s *onlineSlotState) fixEffectiveClock(eligible time.Time, lead time.Duration) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.phase != onlineSlotFuture {
		return false
	}
	s.effective = eligible
	s.cutoff = eligible.Add(-lead)
	s.phase = onlineSlotEffectiveCutoffFixed
	close(s.cutoffReady)
	return true
}

func (s *onlineSlotState) waitForEffectiveClock(done <-chan struct{}) bool {
	select {
	case <-s.cutoffReady:
		return true
	case <-done:
		return false
	}
}

func (s *onlineSlotState) effectiveClock() (time.Time, time.Time) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.effective, s.cutoff
}

func (s *onlineSlotState) tryInstallReal(candidate onlinePreparedRequest, preparedAt time.Time) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.phase != onlineSlotEffectiveCutoffFixed || !preparedAt.Before(s.cutoff) {
		return false
	}
	s.real = &candidate
	s.realCommittedAt = preparedAt
	return true
}

func (s *onlineSlotState) commit() onlinePreparedRequest {
	s.mu.Lock()
	defer s.mu.Unlock()
	item := s.noop
	if s.phase == onlineSlotEffectiveCutoffFixed && s.real != nil &&
		!s.realCommittedAt.IsZero() && s.realCommittedAt.Before(s.cutoff) {
		item = *s.real
	}
	s.phase = onlineSlotLogicallyCommitted
	return item
}

func (s *onlineSlotState) markEmitted() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.phase == onlineSlotLogicallyCommitted {
		s.phase = onlineSlotPhysicallyEmitted
	}
}

// onlinePublicStartLeadPeriods is a public, secret-independent setup budget.
// It gives a pinned framework enough time to reach its first native outbound
// action after SESSION_READY without consuming the H50 admission window.  It
// does not change the 111-slot public lifetime and cannot be extended by
// private work or result readiness.
const onlinePublicStartLeadPeriods = 50

func actionMessage(action ActionSpec) (v7ohttp.PrivateActionMessage, error) {
	kind, err := actionKind(action.ActionKind)
	if err != nil {
		return v7ohttp.PrivateActionMessage{}, err
	}
	authorization, err := json.Marshal(map[string]string{
		"effect_semantics": action.EffectSemantics,
		"policy_id":        action.PolicyID,
	})
	if err != nil {
		return v7ohttp.PrivateActionMessage{}, err
	}
	return v7ohttp.PrivateActionMessage{
		ProtocolVersion: 1,
		Kind:            kind,
		RouteHandle:     []byte(action.RouteHandle),
		OperationID:     []byte(action.OperationID),
		ProtectedArgs:   action.ProtectedArguments,
		Authorization:   authorization,
	}, nil
}

func prepareOnlineRequest(engine *engine, plan Plan, slot v7ohttp.SlotID,
	message v7ohttp.PrivateActionMessage, operationID string, real bool) (onlinePreparedRequest, error) {
	bhttpRequest, err := engine.codec.EncodeKnownLengthRequestBound(
		v7ohttp.InnerSemanticTarget, message, plan.RequestBHTTPBytes, slot,
	)
	if err != nil {
		return onlinePreparedRequest{}, err
	}
	wire, responseContext, err := engine.client.EncapsulateRequest(slot, bhttpRequest)
	if err != nil || len(wire) != plan.RequestFinalBytes {
		return onlinePreparedRequest{}, errors.New("online canonical request final size mismatch")
	}
	if responseContext.Slot() != slot {
		return onlinePreparedRequest{}, errors.New("online OHTTP client context slot mismatch")
	}
	return onlinePreparedRequest{slot: slot, wire: wire, context: responseContext,
		operationID: operationID, real: real}, nil
}

func validateOnlineAction(plan Plan, routes map[string]RouteSpec, action ActionSpec) error {
	if action.OperationID == "" {
		return errors.New("online action has empty operation ID")
	}
	route, ok := routes[action.RouteHandle]
	if !ok {
		return errors.New("online action uses absent private route")
	}
	if route.ActionKind != action.ActionKind || route.EffectSemantics != action.EffectSemantics || route.PolicyID != action.PolicyID {
		return errors.New("online action disagrees with trusted route table")
	}
	if len(action.ProtectedArguments) > plan.RequestBHTTPBytes {
		return errors.New("online protected arguments exceed fixed request capacity")
	}
	return nil
}

// RunOnline runs one fixed public session while accepting future actions over
// trusted local IPC. The startup Plan must not contain an action sequence.
func RunOnline(plan Plan, controlIn io.Reader, controlOut io.Writer) (RunResult, error) {
	if len(plan.Actions) != 0 {
		return RunResult{}, errors.New("online mode forbids future actions in the startup plan")
	}
	if plan.PreparationLeadMS <= 0 || plan.PreparationLeadMS >= plan.RoundPeriodMS {
		return RunResult{}, errors.New("online preparation lead must be public and strictly below the round period")
	}
	if err := bindAdmission(plan); err != nil {
		return RunResult{}, err
	}
	timingIndistinguishability := plan.ProfileClass == TimingIndistinguishabilityProfile
	if err := os.MkdirAll(plan.StateDirectory, 0o700); err != nil {
		return RunResult{}, err
	}
	engine, err := newEngine(plan)
	if err != nil {
		return RunResult{}, err
	}
	emitter := &onlineEmitter{encoder: json.NewEncoder(controlOut)}
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

	period := time.Duration(plan.RoundPeriodMS) * time.Millisecond
	lead := time.Duration(plan.PreparationLeadMS) * time.Millisecond
	// A public start lead gives the trusted framework time to receive
	// SESSION_READY. It is fixed and independent of future action availability.
	t0 := time.Now().Add(onlinePublicStartLeadPeriods * period)
	duplexTiming := plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4" ||
		plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R1" ||
		plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R2"
	duplexTiming = duplexTiming || plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R3"
	duplexTiming = duplexTiming || plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R4"
	duplexTiming = duplexTiming || plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R5"
	duplexTiming = duplexTiming || plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6"
	duplexTiming = duplexTiming || plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R7"
	duplexTiming = duplexTiming || plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8"
	if duplexTiming {
		responsePreparationWorkers := plan.ResponsePreparationWorkers
		if responsePreparationWorkers < 1 {
			responsePreparationWorkers = 1
		}
		responsePublicLag := plan.ResponsePublicLagMS
		if responsePublicLag < 1 {
			responsePublicLag = plan.ResponseInitialReleaseDelayMS
		}
		if responsePublicLag < 1 {
			responsePublicLag = plan.ResponsePreparationLeadMS
		}
		responseClock, clockErr := newGatewayResponseVirtualizer(
			plan.Rounds, period,
			time.Duration(responsePublicLag)*time.Millisecond,
			time.Duration(plan.ResponsePreparationLeadMS)*time.Millisecond,
			responsePreparationWorkers,
			plan.TimingSemanticRevision == "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8",
			processClock,
		)
		if clockErr != nil {
			return RunResult{}, clockErr
		}
		engine.responseClock = responseClock
	}
	slots := make([]*onlineSlotState, plan.Rounds)
	for index := range slots {
		slotID := v7ohttp.SlotID{Session: 1, Slot: uint32(index + 1)}
		message := v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionNoop,
			OperationID: []byte(fmt.Sprintf("noop-%06d", index+1))}
		noop, err := prepareOnlineRequest(engine, plan, slotID, message, "", false)
		if err != nil {
			return RunResult{}, err
		}
		deadline := t0.Add(time.Duration(index) * period)
		slots[index] = newOnlineSlotState(deadline, noop)
	}
	fixSlotClock := func(index int, previousDispatch time.Time) {
		state := slots[index]
		eligible := state.nominalDeadline
		if timingIndistinguishability {
			eligible = effectivePublicEligibility(state.nominalDeadline, previousDispatch, period)
		}
		if !state.fixEffectiveClock(eligible, lead) {
			return
		}
		if timingIndistinguishability {
			engine.setDeliveryCutoff(uint32(index+1), eligible.Add(-lead).UnixNano())
		}
		if engine.responseClock != nil {
			engine.responseClock.setEligibility(uint32(index+1), eligible)
		}
	}
	if timingIndistinguishability {
		// Effective timing slots are frozen one at a time because E_i uses only
		// the previous actual public dispatch.  No private state participates.
		fixSlotClock(0, time.Time{})
	} else {
		// Historical strict/non-timing profiles retain their pre-existing
		// nominal clock.  Every cutoff is known at T0, including after a
		// deliberately failed public slot.
		for index := range slots {
			fixSlotClock(index, time.Time{})
		}
	}
	setupEvents = append(setupEvents,
		PublicSetupEvent{Stage: "PREBUILT_NOOP_TABLE_COMPLETE", MonotonicNS: monotonicNS()},
		PublicSetupEvent{Stage: "T0_ASSIGNED", MonotonicNS: monotonicNS()},
	)

	incoming := make(chan ActionSpec, plan.MaximumRealOperations+1)
	done := make(chan struct{})
	var acceptedMu sync.Mutex
	acceptedIDs := make([]string, 0, plan.MaximumRealOperations)
	resolvedNotAdmitted := make([]string, 0)
	seenOperations := make(map[string]bool)
	controlSubmitted := 0
	go func() {
		decoder := json.NewDecoder(bufio.NewReader(controlIn))
		for {
			var message OnlineControlMessage
			if err := decoder.Decode(&message); err != nil {
				return
			}
			if message.Type != "SUBMIT_RESOLVED_ACTION" || message.Action == nil {
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", Reason: "invalid trusted control message"})
				continue
			}
			action := *message.Action
			if err := validateOnlineAction(plan, engine.routes, action); err != nil {
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: err.Error()})
				continue
			}
			acceptedMu.Lock()
			duplicate := seenOperations[action.OperationID]
			if !duplicate {
				seenOperations[action.OperationID] = true
				controlSubmitted++
			}
			overCapacity := controlSubmitted > plan.MaximumRealOperations
			acceptedMu.Unlock()
			if duplicate || overCapacity {
				reason := "duplicate operation ID"
				if overCapacity {
					reason = "PROFILE_CAPACITY_EXCEEDED"
				}
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: reason})
				continue
			}
			select {
			case incoming <- action:
			case <-done:
				emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: "SESSION_CLOSED"})
				return
			}
		}
	}()

	// One trusted preparation worker preserves causal arrival order. It assigns
	// a private action only to a still-future public admission slot. Unused
	// candidate OHTTP contexts are discarded and never reused.
	go func() {
		nextSlot := 0
		for {
			select {
			case action := <-incoming:
				admitted := false
				for nextSlot < plan.AdmissionRounds {
					index := nextSlot
					nextSlot++
					state := slots[index]
					if !state.waitForEffectiveClock(done) {
						return
					}
					_, cutoff := state.effectiveClock()
					if !time.Now().Before(cutoff) {
						continue
					}
					message, err := actionMessage(action)
					if err != nil {
						break
					}
					candidate, err := prepareOnlineRequest(engine, plan, state.noop.slot, message, action.OperationID, true)
					if err != nil {
						break
					}
					commitTime := time.Now()
					admitted = state.tryInstallReal(candidate, commitTime)
					if admitted {
						acceptedMu.Lock()
						acceptedIDs = append(acceptedIDs, action.OperationID)
						acceptedMu.Unlock()
						emitter.emit(OnlineControlEvent{Type: "ACTION_ACCEPTED", OperationID: action.OperationID, Round: index + 1})
						break
					}
				}
				if !admitted {
					acceptedMu.Lock()
					resolvedNotAdmitted = append(resolvedNotAdmitted, action.OperationID)
					acceptedMu.Unlock()
					emitter.emit(OnlineControlEvent{Type: "ACTION_REJECTED", OperationID: action.OperationID, Reason: "PROFILE_ADMISSION_CLOSED"})
				}
			case <-done:
				return
			}
		}
	}()

	emitter.emit(OnlineControlEvent{Type: "SESSION_READY"})
	type slotResponse struct {
		item             onlinePreparedRequest
		wire             []byte
		httpVersion      string
		httpSubmissionNS int64
		err              error
		diagnostic       *TransportDiagnostic
	}
	responses := make(chan slotResponse, plan.Rounds)
	var responseWG sync.WaitGroup
	launches := make([]SlotLaunch, 0, plan.Rounds)
	schedulerIncidents := make([]SchedulerIncident, 0)
	schedulerConfiguration := SchedulerConfiguration{PacerCPU: -1}
	submitted := 0
	tolerance := time.Duration(plan.SchedulerToleranceMS) * time.Millisecond
	if tolerance <= 0 {
		tolerance = 2 * period
	}
	schedulerDone := make(chan struct{})
	infrastructureLivenessFailure := false
	go func() {
		defer close(schedulerDone)
		pacer, pacerErr := newPublicPacer()
		if pacerErr != nil {
			schedulerConfiguration = SchedulerConfiguration{
				Implementation: "PACER_INITIALIZATION_FAILED",
				PacerCPU:       -1,
				WaitError:      pacerErr.Error(),
			}
			for _, state := range slots {
				nominalCutoff := state.nominalDeadline.Add(-lead)
				launches = append(launches, SlotLaunch{
					Session: 1, Slot: state.noop.slot.Slot,
					DeadlineNS:          state.nominalDeadline.Sub(processClock).Nanoseconds(),
					PreparationCutoffNS: nominalCutoff.Sub(processClock).Nanoseconds(),
					ScheduleMiss:        true,
				})
			}
			close(responses)
			return
		}
		pacerWaitError := ""
		defer func() {
			schedulerConfiguration = pacer.Close()
			schedulerConfiguration.WaitError = pacerWaitError
		}()
		hostBefore := schedulerHostSnapshot()
		previousDispatch := time.Time{}
		livenessDeadline := processClock.Add(time.Duration(plan.PublicSessionLivenessCapMS) * time.Millisecond)
		for index, state := range slots {
			if !state.waitForEffectiveClock(done) {
				break
			}
			eligible, cutoff := state.effectiveClock()
			if err := pacer.WaitUntil(cutoff); err != nil {
				pacerWaitError = err.Error()
				for _, remainingState := range slots[index:] {
					remainingCutoff := remainingState.nominalDeadline.Add(-lead)
					launches = append(launches, SlotLaunch{
						Session: 1, Slot: remainingState.noop.slot.Slot,
						DeadlineNS:          remainingState.nominalDeadline.Sub(processClock).Nanoseconds(),
						PreparationCutoffNS: remainingCutoff.Sub(processClock).Nanoseconds(),
						ScheduleMiss:        true,
					})
				}
				break
			}
			preparationWake := time.Now()
			incidentBefore := hostBefore
			if preparationWake.Sub(cutoff) > tolerance {
				incidentBefore = schedulerHostSnapshot()
			}
			// NOOP is the precommitted default. A REAL payload may replace it
			// only if preparation completed before the effective public cutoff.
			// Late physical emission never consults newly eligible private state.
			item := state.commit()
			if item.real {
				emitter.emit(OnlineControlEvent{Type: "ACTION_ADMITTED", OperationID: item.operationID, Round: index + 1})
				engine.record(PrivateEvent{OperationID: item.operationID, Stage: "ONLINE_ACTION_ADMITTED", Round: index + 1})
			}
			sleepEntry := time.Now()
			if err := pacer.WaitUntil(eligible); err != nil {
				pacerWaitError = err.Error()
				for _, remainingState := range slots[index:] {
					remainingCutoff := remainingState.nominalDeadline.Add(-lead)
					launches = append(launches, SlotLaunch{
						Session: 1, Slot: remainingState.noop.slot.Slot,
						DeadlineNS:          remainingState.nominalDeadline.Sub(processClock).Nanoseconds(),
						PreparationCutoffNS: remainingCutoff.Sub(processClock).Nanoseconds(),
						ScheduleMiss:        true,
					})
				}
				break
			}
			sleepWake := time.Now()
			if plan.FaultSchedulerStallSlot == index+1 && plan.FaultSchedulerStallMS > 0 {
				time.Sleep(time.Duration(plan.FaultSchedulerStallMS) * time.Millisecond)
			}
			dispatchTime := time.Now()
			if timingIndistinguishability && dispatchTime.After(livenessDeadline) {
				infrastructureLivenessFailure = true
				break
			}
			slip := dispatchTime.Sub(state.nominalDeadline)
			launch := SlotLaunch{
				Session: 1, Slot: uint32(index + 1),
				DeadlineNS:            state.nominalDeadline.Sub(processClock).Nanoseconds(),
				EligibleNS:            eligible.Sub(processClock).Nanoseconds(),
				PreparationCutoffNS:   cutoff.Sub(processClock).Nanoseconds(),
				PreparationWakeNS:     preparationWake.Sub(processClock).Nanoseconds(),
				PreparationLatenessNS: preparationWake.Sub(cutoff).Nanoseconds(),
				SleepEntryNS:          sleepEntry.Sub(processClock).Nanoseconds(),
				SleepWakeNS:           sleepWake.Sub(processClock).Nanoseconds(),
				DispatchNS:            dispatchTime.Sub(processClock).Nanoseconds(),
				WakeLatenessNS:        sleepWake.Sub(state.nominalDeadline).Nanoseconds(),
				DispatchLatenessNS:    dispatchTime.Sub(state.nominalDeadline).Nanoseconds(),
				LaunchSlipNS:          slip.Nanoseconds(),
			}
			launch.ToleranceExceeded = slip > tolerance
			if slip >= period {
				launch.ScheduleMiss = true
				hostAfter := schedulerHostSnapshot()
				schedulerIncidents = append(schedulerIncidents, SchedulerIncident{
					Slot: launch.Slot, DeadlineNS: launch.DeadlineNS,
					WakeLatenessNS:     launch.WakeLatenessNS,
					DispatchLatenessNS: launch.DispatchLatenessNS,
					LaunchSlipNS:       launch.LaunchSlipNS,
					Before:             incidentBefore, After: hostAfter,
				})
				hostBefore = hostAfter
				if !timingIndistinguishability {
					launches = append(launches, launch)
					continue
				}
			}
			launch.SubmitNS = dispatchTime.Sub(processClock).Nanoseconds()
			launch.Emitted = true
			launches = append(launches, launch)
			previousDispatch = dispatchTime
			state.markEmitted()
			if index+1 < len(slots) {
				fixSlotClock(index+1, previousDispatch)
			}
			submitted++
			responseWG.Add(1)
			go func(value onlinePreparedRequest) {
				defer responseWG.Done()
				request, requestErr := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(value.wire))
				if requestErr != nil {
					responses <- slotResponse{item: value, err: requestErr}
					return
				}
				request.Header.Set("Content-Type", v8.OHTTPRequestContentType)
				request.Header.Set("X-AgentTool-Public-Session", "1")
				request.Header.Set("X-AgentTool-Public-Slot", strconv.FormatUint(uint64(value.slot.Slot), 10))
				request.ContentLength = int64(len(value.wire))
				httpSubmissionNS := time.Since(processClock).Nanoseconds()
				response, requestErr := clientHTTP.Do(request)
				if requestErr != nil {
					responses <- slotResponse{item: value, err: requestErr, httpSubmissionNS: httpSubmissionNS}
					return
				}
				responseWire, readErr := io.ReadAll(io.LimitReader(response.Body, int64(plan.ResponseFinalBytes+1)))
				response.Body.Close()
				if readErr != nil || response.StatusCode != http.StatusOK || len(responseWire) != plan.ResponseFinalBytes {
					failureClass := "RESPONSE_BODY_LENGTH_MISMATCH"
					if readErr != nil {
						failureClass = "RESPONSE_READ_ERROR"
					} else if response.StatusCode != http.StatusOK {
						failureClass = "GATEWAY_NON_200"
					}
					diagnostic := &TransportDiagnostic{Slot: value.slot.Slot, HTTPStatus: response.StatusCode,
						ObservedBodyBytes: len(responseWire), ExpectedBodyBytes: plan.ResponseFinalBytes,
						FailureClass: failureClass}
					if readErr != nil {
						diagnostic.Error = readErr.Error()
					}
					responses <- slotResponse{item: value,
						err: fmt.Errorf("online canonical response validation failed: slot=%d http_status=%d observed_body_bytes=%d expected_body_bytes=%d class=%s",
							value.slot.Slot, response.StatusCode, len(responseWire), plan.ResponseFinalBytes, failureClass),
						diagnostic: diagnostic, httpSubmissionNS: httpSubmissionNS}
					return
				}
				responses <- slotResponse{item: value, wire: responseWire, httpVersion: response.Proto, httpSubmissionNS: httpSubmissionNS}
			}(item)
		}
		responseWG.Wait()
		close(responses)
	}()

	results := make([]ClientResult, 0, plan.MaximumRealOperations)
	httpSubmissions := make(map[uint32]int64, plan.Rounds)
	transportFailure := false
	transportDiagnostics := make([]TransportDiagnostic, 0)
	for response := range responses {
		if response.httpSubmissionNS != 0 {
			httpSubmissions[response.item.slot.Slot] = response.httpSubmissionNS
		}
		if response.err != nil || response.httpVersion != "HTTP/2.0" {
			transportFailure = true
			if response.diagnostic != nil {
				transportDiagnostics = append(transportDiagnostics, *response.diagnostic)
			} else if response.err != nil {
				transportDiagnostics = append(transportDiagnostics, TransportDiagnostic{Slot: response.item.slot.Slot,
					FailureClass: "TRANSPORT_ERROR", Error: response.err.Error()})
			}
			continue
		}
		opened, err := engine.client.DecapsulateResponse(response.item.context, response.wire)
		if err != nil {
			transportFailure = true
			continue
		}
		decoded, innerSlot, err := engine.codec.DecodeKnownLengthResponseBound(opened)
		if err != nil || innerSlot != response.item.slot {
			transportFailure = true
			continue
		}
		if decoded.Status != v9ohttp.StatusWait {
			result := ClientResult{OperationID: decoded.OperationID, Status: decoded.Status,
				Payload: decoded.Payload, Round: int(response.item.slot.Slot)}
			results = append(results, result)
			engine.record(PrivateEvent{OperationID: decoded.OperationID, Stage: "CLIENT_BHTTP_DECODED",
				Status: fmt.Sprintf("%d", decoded.Status), Round: int(response.item.slot.Slot)})
			emitter.emit(OnlineControlEvent{Type: "RESULT_AVAILABLE", OperationID: decoded.OperationID, Round: int(response.item.slot.Slot), Result: &result})
		}
	}
	for index := range launches {
		launches[index].HTTPSubmissionNS = httpSubmissions[launches[index].Slot]
	}
	gatewayResponseReleases := []gatewayResponseRelease(nil)
	if engine.responseClock != nil {
		gatewayResponseReleases = engine.responseClock.wait()
	}
	<-schedulerDone
	engine.workers.Wait()
	engine.responseAcks.Wait()
	close(done)
	sort.Slice(results, func(i, j int) bool { return results[i].Round < results[j].Round })
	delivered := make(map[string]bool, len(results))
	for _, result := range results {
		delivered[result.OperationID] = true
	}
	acceptedMu.Lock()
	acceptedCopy := append([]string(nil), acceptedIDs...)
	notAdmittedCopy := append([]string(nil), resolvedNotAdmitted...)
	acceptedMu.Unlock()
	pending := make([]string, 0)
	for _, operationID := range acceptedCopy {
		if !delivered[operationID] {
			pending = append(pending, operationID)
		}
	}
	scheduleMisses := 0
	for _, launch := range launches {
		if launch.ScheduleMiss {
			scheduleMisses++
		}
	}
	relayEvents := relay.Events()
	releaseOpportunities := len(gatewayResponseReleases)
	releaseAttempts := 0
	successfulWrites := 0
	if engine.responseClock != nil {
		for _, release := range gatewayResponseReleases {
			if release.ReleaseAttempted {
				releaseAttempts++
			}
			if release.WriteCompleted {
				successfulWrites++
			}
		}
	} else {
		releaseOpportunities = submitted
		releaseAttempts = submitted
		successfulWrites = len(relayEvents)
	}
	transcriptComplete := successfulWrites == plan.Rounds &&
		exactRelayPublicSlotInventory(relayEvents, plan.Rounds)
	status := "COMPLETE"
	if infrastructureLivenessFailure {
		status = "INFRASTRUCTURE_LIVENESS_FAILURE"
	} else if scheduleMisses > 0 && !timingIndistinguishability {
		status = "SESSION_SCHEDULE_FAILURE"
	} else if transportFailure || submitted != plan.Rounds || !transcriptComplete {
		status = "SESSION_TRANSPORT_FAILURE"
	} else if len(pending) > 0 {
		status = "SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT"
	}
	result := RunResult{ProfileID: plan.ProfileID, ProfileClass: plan.ProfileClass, Rounds: plan.Rounds, Admitted: len(acceptedCopy),
		ProviderInvocations: engine.providerCalls.Load(), DummyProviderOperations: 0,
		Results: results, PrivateEvents: append([]PrivateEvent(nil), engine.events...),
		PublicRelayEvents: relayEvents, AfterCutoffOperations: []string{"atomic slot snapshot", "PreparedSlot.Send", "one fixed-size writer.Write", "byte-count validation"},
		RequestFinalBytes: plan.RequestFinalBytes, ResponseFinalBytes: plan.ResponseFinalBytes,
		SessionStatus: status, PublicSetupEvents: setupEvents, SlotLaunches: launches,
		ScheduleMisses: scheduleMisses, NominalLateCells: scheduleMisses, EmittedCells: successfulWrites,
		PublicTranscriptComplete: transcriptComplete, InfrastructureLivenessFailure: infrastructureLivenessFailure,
		PendingOperationIDs: pending, SilentCommittedLosses: 0,
		ClientRelayHTTPVersion: preconnectProto, RelayGatewayHTTPVersion: "HTTP/2.0",
		OnlineMode: true, StartupActionCount: 0, AcceptedOperationIDs: acceptedCopy,
		ResolvedNotAdmittedIDs: notAdmittedCopy, FrameworkWaiterIDs: append([]string(nil), pending...),
		TransportDiagnostics: transportDiagnostics, ProviderDiagnostics: engine.providerDiagnostics(),
		SchedulerIncidents: schedulerIncidents, SchedulerConfiguration: schedulerConfiguration,
		GatewayResponseReleases:      gatewayResponseReleases,
		ResponseReleaseOpportunities: releaseOpportunities,
		ResponseReleaseAttempts:      releaseAttempts, SuccessfulResponseWrites: successfulWrites,
		RelayApplicationReceivedCells: len(relayEvents)}
	if status == "COMPLETE" {
		emitter.emit(OnlineControlEvent{Type: "SESSION_COMPLETE"})
	} else {
		emitter.emit(OnlineControlEvent{Type: "SESSION_FAILURE", Reason: status})
	}
	return result, nil
}
