package canonicalv9

import (
	"errors"
	"net/http"
	"time"

	"common-action-gateway-v2/v8"
)

type responseEligibility struct {
	slot     uint32
	eligible time.Time
}

type gatewayResponseRequest struct {
	slot           uint32
	requestArrival time.Time
	prepare        func(time.Time) (v8.PreparedSlot, error)
	writer         http.ResponseWriter
	done           chan error
}

type gatewayResponseRelease struct {
	Slot             uint32 `json:"slot"`
	EligibilityNS    int64  `json:"eligibility_ns"`
	RequestArrivalNS int64  `json:"request_arrival_ns"`
	CommitmentNS     int64  `json:"commitment_ns"`
	ReleaseNS        int64  `json:"release_ns"`
	ActualReleaseNS  int64  `json:"actual_release_ns"`
	PreparationEndNS int64  `json:"preparation_end_ns"`
	DeadlineMiss     bool   `json:"deadline_miss"`
}

// gatewayResponseVirtualizer is the trusted reverse public clock. One public
// goroutine commits and releases responses in slot order. Private readiness is
// consulted only by the bounded prepare callback at the already-fixed cutoff.
type gatewayResponseVirtualizer struct {
	rounds       int
	period       time.Duration
	lead         time.Duration
	processClock time.Time
	eligibility  chan responseEligibility
	requests     chan gatewayResponseRequest
	releases     chan gatewayResponseRelease
	complete     chan struct{}
}

func newGatewayResponseVirtualizer(rounds int, period, lead time.Duration, processClock time.Time) (*gatewayResponseVirtualizer, error) {
	if rounds < 1 || period <= 0 || lead <= 0 || lead >= period {
		return nil, errors.New("invalid duplex Gateway response clock")
	}
	value := &gatewayResponseVirtualizer{
		rounds: rounds, period: period, lead: lead, processClock: processClock,
		eligibility: make(chan responseEligibility, rounds),
		requests:    make(chan gatewayResponseRequest, rounds),
		releases:    make(chan gatewayResponseRelease, rounds),
		complete:    make(chan struct{}),
	}
	ready := make(chan error, 1)
	go value.run(ready)
	if err := <-ready; err != nil {
		return nil, err
	}
	return value, nil
}

func maxPublicTime(values ...time.Time) time.Time {
	result := values[0]
	for _, value := range values[1:] {
		if value.After(result) {
			result = value
		}
	}
	return result
}

func gatewayResponseDeadline(eligible, requestArrival, previousRelease time.Time,
	period, lead time.Duration) time.Time {
	release := maxPublicTime(eligible.Add(lead), requestArrival.Add(lead))
	if !previousRelease.IsZero() {
		release = maxPublicTime(release, previousRelease.Add(period))
	}
	return release
}

func (v *gatewayResponseVirtualizer) run(ready chan<- error) {
	pacer, err := newPublicPacer()
	ready <- err
	if err != nil {
		close(v.complete)
		return
	}
	defer func() {
		_ = pacer.Close()
		close(v.releases)
		close(v.complete)
	}()
	eligibilities := make(map[uint32]time.Time, v.rounds)
	requests := make(map[uint32]gatewayResponseRequest, v.rounds)
	previousRelease := time.Time{}
	for slot := uint32(1); slot <= uint32(v.rounds); slot++ {
		for eligibilities[slot].IsZero() || requests[slot].done == nil {
			select {
			case item := <-v.eligibility:
				eligibilities[item.slot] = item.eligible
			case item := <-v.requests:
				requests[item.slot] = item
			}
		}
		request := requests[slot]
		release := gatewayResponseDeadline(
			eligibilities[slot], request.requestArrival, previousRelease, v.period, v.lead,
		)
		commitment := release.Add(-v.lead)
		if err := pacer.WaitUntil(commitment); err != nil {
			request.done <- err
			return
		}
		prepared, prepareErr := request.prepare(commitment)
		preparationEnd := time.Now()
		if prepareErr == nil {
			prepareErr = pacer.WaitUntil(release)
		}
		actualRelease := time.Now()
		if prepareErr == nil {
			request.writer.WriteHeader(http.StatusOK)
			prepareErr = prepared.Send(request.writer)
		}
		previousRelease = actualRelease
		v.releases <- gatewayResponseRelease{
			Slot:             slot,
			EligibilityNS:    eligibilities[slot].Sub(v.processClock).Nanoseconds(),
			RequestArrivalNS: request.requestArrival.Sub(v.processClock).Nanoseconds(),
			CommitmentNS:     commitment.Sub(v.processClock).Nanoseconds(),
			ReleaseNS:        release.Sub(v.processClock).Nanoseconds(),
			ActualReleaseNS:  actualRelease.Sub(v.processClock).Nanoseconds(),
			PreparationEndNS: preparationEnd.Sub(v.processClock).Nanoseconds(),
			DeadlineMiss:     preparationEnd.After(release),
		}
		request.done <- prepareErr
	}
}

func (v *gatewayResponseVirtualizer) setEligibility(slot uint32, eligible time.Time) {
	v.eligibility <- responseEligibility{slot: slot, eligible: eligible}
}

func (v *gatewayResponseVirtualizer) release(slot uint32, requestArrival time.Time,
	prepare func(time.Time) (v8.PreparedSlot, error), writer http.ResponseWriter) error {
	done := make(chan error, 1)
	request := gatewayResponseRequest{slot: slot, requestArrival: requestArrival,
		prepare: prepare, writer: writer, done: done}
	select {
	case v.requests <- request:
	case <-v.complete:
		return errors.New("duplex Gateway response clock stopped")
	}
	select {
	case err := <-done:
		return err
	case <-v.complete:
		select {
		case err := <-done:
			return err
		default:
			return errors.New("duplex Gateway response clock stopped")
		}
	}
}

func (v *gatewayResponseVirtualizer) wait() []gatewayResponseRelease {
	<-v.complete
	result := make([]gatewayResponseRelease, 0, v.rounds)
	for item := range v.releases {
		result = append(result, item)
	}
	return result
}
