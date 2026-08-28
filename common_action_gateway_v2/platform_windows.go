//go:build windows

package gatewayv2

import (
	"fmt"
	"syscall"
	"time"
)

func MonotonicNowNS() int64 { return time.Now().UnixNano() }

func WaitUntilNS(deadline int64) int64 {
	for {
		now := MonotonicNowNS()
		remaining := deadline - now
		if remaining <= 0 {
			return now
		}
		if remaining > int64(2*time.Millisecond) {
			time.Sleep(time.Duration(remaining - int64(time.Millisecond)))
		} else {
			time.Sleep(0)
		}
	}
}

func ApplyPacerIsolation(cpu int, realtime bool) IsolationStatus {
	status := IsolationStatus{Platform: "windows", RequestedCPU: cpu, RealtimeRequested: realtime,
		ReferenceTimingPlatform: false, Note: "functional fallback; Windows cannot establish timing closure"}
	if cpu < 0 {
		status.AffinityDetail = "not requested"
		return status
	}
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	getCurrentProcess := kernel32.NewProc("GetCurrentProcess")
	setAffinity := kernel32.NewProc("SetProcessAffinityMask")
	handle, _, _ := getCurrentProcess.Call()
	result, _, err := setAffinity.Call(handle, uintptr(1)<<uint(cpu))
	if result == 0 {
		status.AffinityDetail = fmt.Sprintf("failed: %v", err)
	} else {
		status.AffinityApplied = true
		status.AffinityDetail = "SetProcessAffinityMask applied"
	}
	status.RealtimeDetail = "SCHED_FIFO unavailable on Windows fallback"
	return status
}

func ApplyWorkerAffinity(cpu int) IsolationStatus { return ApplyPacerIsolation(cpu, false) }
