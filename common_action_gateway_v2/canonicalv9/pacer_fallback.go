//go:build !linux

package canonicalv9

import (
	"runtime"
	"time"
)

type fallbackAbsolutePacer struct {
	config SchedulerConfiguration
}

func newPublicPacer() (publicPacer, error) {
	runtime.LockOSThread()
	return &fallbackAbsolutePacer{config: SchedulerConfiguration{
		Implementation:    "GO_ABSOLUTE_TIME_UNTIL_FALLBACK",
		Clock:             "GO_MONOTONIC",
		AbsoluteDeadlines: true,
		OSThreadLocked:    true,
		PacerCPU:          -1,
	}}, nil
}

func (pacer *fallbackAbsolutePacer) WaitUntil(deadline time.Time) error {
	if remaining := time.Until(deadline); remaining > 0 {
		time.Sleep(remaining)
	}
	return nil
}

func (pacer *fallbackAbsolutePacer) Close() SchedulerConfiguration {
	runtime.UnlockOSThread()
	return pacer.config
}
