//go:build !linux

package canonicalv9

import (
	"os"
	"runtime"
)

func schedulerHostSnapshot() SchedulerHostSnapshot {
	var memory runtime.MemStats
	runtime.ReadMemStats(&memory)
	return SchedulerHostSnapshot{
		PID:            os.Getpid(),
		TID:            -1,
		CPU:            -1,
		GOMAXPROCS:     runtime.GOMAXPROCS(0),
		GCCycles:       memory.NumGC,
		GCPauseTotalNS: memory.PauseTotalNs,
		Unavailable:    []string{"linux_proc_scheduler_diagnostics"},
	}
}
