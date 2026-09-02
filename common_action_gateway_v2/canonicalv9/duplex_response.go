package canonicalv9

import (
	"errors"
	"net/http"
	"sync"
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
	commit         func(time.Time) (func() (v8.PreparedSlot, error), error)
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

type committedGatewayResponse struct {
	request        gatewayResponseRequest
	eligibility    time.Time
	commitment     time.Time
	plannedRelease time.Time
	prepared       <-chan preparedGatewayResponse
}

type preparedGatewayResponse struct {
	prepared       v8.PreparedSlot
	preparationEnd time.Time
	err            error
}

type gatewayResponsePreparationJob struct {
	prepare func() (v8.PreparedSlot, error)
	result  chan<- preparedGatewayResponse
}

// gatewayResponseVirtualizer is the trusted reverse public clock. A fixed
// commitment/preparation lane and a distinct fixed release lane run as a
// pipeline. The release lane never consults private readiness.
type gatewayResponseVirtualizer struct {
	rounds       int
	period       time.Duration
	lead         time.Duration
	workers      int
	processClock time.Time
	eligibility  chan responseEligibility
	requests     chan gatewayResponseRequest
	releases     chan gatewayResponseRelease
	complete     chan struct{}
}

func newGatewayResponseVirtualizer(rounds int, period, lead time.Duration, workers int,
	processClock time.Time) (*gatewayResponseVirtualizer, error) {
	if rounds < 1 || period <= 0 || lead <= 0 || workers < 1 {
		return nil, errors.New("invalid duplex Gateway response clock")
	}
	value := &gatewayResponseVirtualizer{
		rounds: rounds, period: period, lead: lead, workers: workers, processClock: processClock,
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
	commitmentPacer, err := newPublicPacer()
	if err != nil {
		ready <- err
		close(v.complete)
		return
	}
	releasePacer, err := newPublicPacer()
	if err != nil {
		_ = commitmentPacer.Close()
		ready <- err
		close(v.complete)
		return
	}
	ready <- nil
	committed := make(chan committedGatewayResponse, v.rounds)
	preparationJobs := make(chan gatewayResponsePreparationJob, v.rounds)
	var preparationWorkers sync.WaitGroup
	for lane := 0; lane < v.workers; lane++ {
		preparationWorkers.Add(1)
		go func() {
			defer preparationWorkers.Done()
			for job := range preparationJobs {
				prepared, prepareErr := job.prepare()
				job.result <- preparedGatewayResponse{
					prepared: prepared, preparationEnd: time.Now(), err: prepareErr,
				}
				close(job.result)
			}
		}()
	}
	releaseDone := make(chan struct{})
	go v.releaseCommitted(releasePacer, committed, releaseDone)
	defer func() {
		close(preparationJobs)
		preparationWorkers.Wait()
		close(committed)
		<-releaseDone
		_ = commitmentPacer.Close()
		close(v.releases)
		close(v.complete)
	}()
	eligibilities := make(map[uint32]time.Time, v.rounds)
	requests := make(map[uint32]gatewayResponseRequest, v.rounds)
	previousPlannedRelease := time.Time{}
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
		plannedRelease := gatewayResponseDeadline(
			eligibilities[slot], request.requestArrival, previousPlannedRelease, v.period, v.lead,
		)
		commitment := plannedRelease.Add(-v.lead)
		if err := commitmentPacer.WaitUntil(commitment); err != nil {
			request.done <- err
			return
		}
		prepare, commitErr := request.commit(commitment)
		prepared := make(chan preparedGatewayResponse, 1)
		if commitErr != nil {
			prepared <- preparedGatewayResponse{preparationEnd: time.Now(), err: commitErr}
			close(prepared)
		} else {
			preparationJobs <- gatewayResponsePreparationJob{prepare: prepare, result: prepared}
		}
		committed <- committedGatewayResponse{
			request: request, eligibility: eligibilities[slot], commitment: commitment,
			plannedRelease: plannedRelease, prepared: prepared,
		}
		previousPlannedRelease = plannedRelease
	}
}

func (v *gatewayResponseVirtualizer) releaseCommitted(pacer publicPacer,
	committed <-chan committedGatewayResponse, done chan<- struct{}) {
	defer func() {
		_ = pacer.Close()
		close(done)
	}()
	previousActualRelease := time.Time{}
	for item := range committed {
		release := item.plannedRelease
		if !previousActualRelease.IsZero() {
			release = maxPublicTime(release, previousActualRelease.Add(v.period))
		}
		releaseErr := pacer.WaitUntil(release)
		preparedResult := preparedGatewayResponse{}
		if releaseErr == nil {
			select {
			case preparedResult = <-item.prepared:
				releaseErr = preparedResult.err
			default:
				preparedResult.preparationEnd = time.Now()
				releaseErr = errors.New("duplex Gateway response preparation missed public release")
			}
		}
		deadlineMiss := preparedResult.preparationEnd.After(release)
		if deadlineMiss && releaseErr == nil {
			releaseErr = errors.New("duplex Gateway response preparation missed public release")
		}
		actualRelease := time.Now()
		if releaseErr == nil {
			// Capture the application-emission boundary immediately before the
			// fixed public write. Sending the bytes must not redefine the
			// observer timestamp as a post-write completion timestamp.
			actualRelease = time.Now()
			item.request.writer.WriteHeader(http.StatusOK)
			releaseErr = preparedResult.prepared.Send(item.request.writer)
		}
		previousActualRelease = actualRelease
		v.releases <- gatewayResponseRelease{
			Slot:             item.request.slot,
			EligibilityNS:    item.eligibility.Sub(v.processClock).Nanoseconds(),
			RequestArrivalNS: item.request.requestArrival.Sub(v.processClock).Nanoseconds(),
			CommitmentNS:     item.commitment.Sub(v.processClock).Nanoseconds(),
			ReleaseNS:        release.Sub(v.processClock).Nanoseconds(),
			ActualReleaseNS:  actualRelease.Sub(v.processClock).Nanoseconds(),
			PreparationEndNS: preparedResult.preparationEnd.Sub(v.processClock).Nanoseconds(),
			DeadlineMiss:     deadlineMiss,
		}
		item.request.done <- releaseErr
	}
}

func (v *gatewayResponseVirtualizer) setEligibility(slot uint32, eligible time.Time) {
	v.eligibility <- responseEligibility{slot: slot, eligible: eligible}
}

func (v *gatewayResponseVirtualizer) release(slot uint32, requestArrival time.Time,
	commit func(time.Time) (func() (v8.PreparedSlot, error), error), writer http.ResponseWriter) error {
	done := make(chan error, 1)
	request := gatewayResponseRequest{slot: slot, requestArrival: requestArrival,
		commit: commit, writer: writer, done: done}
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
