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

type jitterTolerantSlotDecision struct {
	NominalNS  int64
	EligibleNS int64
	DispatchNS int64
	Late       bool
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

// evaluateJitterTolerantSlots models the public no-drop/no-burst recurrence.
// Inputs are only the public nominal schedule and externally realized dispatch
// opportunities; no action, result, or secret label participates.
func evaluateJitterTolerantSlots(t0NS, periodNS int64, opportunitiesNS []int64) []jitterTolerantSlotDecision {
	decisions := make([]jitterTolerantSlotDecision, len(opportunitiesNS))
	previousDispatch := int64(0)
	for index, opportunity := range opportunitiesNS {
		nominal := t0NS + int64(index)*periodNS
		eligible := nominal
		if index > 0 && previousDispatch+periodNS > eligible {
			eligible = previousDispatch + periodNS
		}
		dispatch := opportunity
		if dispatch < eligible {
			dispatch = eligible
		}
		decisions[index] = jitterTolerantSlotDecision{
			NominalNS: nominal, EligibleNS: eligible, DispatchNS: dispatch,
			Late: dispatch-nominal >= periodNS, Transmit: true,
		}
		previousDispatch = dispatch
	}
	return decisions
}
