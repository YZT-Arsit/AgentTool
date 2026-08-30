package canonicalv9

import "time"

// publicPacer owns the public-slot timing mechanism. Implementations wait for
// independently derived absolute deadlines; a prior wake delay never shifts a
// later deadline.
type publicPacer interface {
	WaitUntil(time.Time) error
	Close() SchedulerConfiguration
}

type absoluteSlotDecision struct {
	DeadlineNS int64
	DispatchNS int64
	Missed     bool
	Transmit   bool
}

// evaluateAbsoluteSlots is a deterministic model used to audit miss and
// no-catch-up rules independently of host scheduler timing.
func evaluateAbsoluteSlots(t0NS, periodNS int64, dispatchNS []int64) []absoluteSlotDecision {
	decisions := make([]absoluteSlotDecision, len(dispatchNS))
	for index, dispatch := range dispatchNS {
		deadline := t0NS + int64(index)*periodNS
		missed := dispatch-deadline >= periodNS
		decisions[index] = absoluteSlotDecision{
			DeadlineNS: deadline,
			DispatchNS: dispatch,
			Missed:     missed,
			Transmit:   !missed,
		}
	}
	return decisions
}
