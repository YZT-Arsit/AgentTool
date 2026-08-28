//go:build linux

package gatewayv2

import (
	"fmt"
	"syscall"
	"unsafe"
)

const clockMonotonic = 1
const timerAbstime = 1
const schedFIFO = 1

func MonotonicNowNS() int64 {
	var ts syscall.Timespec
	_, _, errno := syscall.RawSyscall(syscall.SYS_CLOCK_GETTIME, clockMonotonic, uintptr(unsafe.Pointer(&ts)), 0)
	if errno != 0 {
		panic(errno)
	}
	return ts.Sec*1_000_000_000 + ts.Nsec
}

func WaitUntilNS(deadline int64) int64 {
	ts := syscall.Timespec{Sec: deadline / 1_000_000_000, Nsec: deadline % 1_000_000_000}
	for {
		_, _, errno := syscall.RawSyscall6(syscall.SYS_CLOCK_NANOSLEEP, clockMonotonic, timerAbstime,
			uintptr(unsafe.Pointer(&ts)), 0, 0, 0)
		if errno == 0 {
			return MonotonicNowNS()
		}
		if errno != syscall.EINTR {
			panic(errno)
		}
	}
}

type schedParam struct{ Priority int32 }

func ApplyPacerIsolation(cpu int, realtime bool) IsolationStatus {
	status := IsolationStatus{Platform: "linux", RequestedCPU: cpu, RealtimeRequested: realtime,
		ReferenceTimingPlatform: false}
	if cpu >= 0 {
		mask := make([]byte, 128)
		mask[cpu/8] |= 1 << uint(cpu%8)
		_, _, errno := syscall.RawSyscall(syscall.SYS_SCHED_SETAFFINITY, 0, uintptr(len(mask)), uintptr(unsafe.Pointer(&mask[0])))
		if errno == 0 {
			status.AffinityApplied = true
			status.AffinityDetail = "sched_setaffinity applied"
		} else {
			status.AffinityDetail = fmt.Sprintf("sched_setaffinity failed: %v", errno)
		}
	} else {
		status.AffinityDetail = "not requested"
	}
	if realtime {
		param := schedParam{Priority: 10}
		_, _, errno := syscall.RawSyscall(syscall.SYS_SCHED_SETSCHEDULER, 0, schedFIFO, uintptr(unsafe.Pointer(&param)))
		if errno == 0 {
			status.RealtimeApplied = true
			status.RealtimeDetail = "SCHED_FIFO priority 10 applied"
		} else {
			status.RealtimeDetail = fmt.Sprintf("SCHED_FIFO unavailable: %v", errno)
		}
	} else {
		status.RealtimeDetail = "not requested"
	}
	status.ReferenceTimingPlatform = status.AffinityApplied && status.RealtimeApplied
	if !status.ReferenceTimingPlatform {
		status.Note = "Linux alone is insufficient; dedicated affinity and requested real-time scheduling were not both established"
	}
	return status
}

func ApplyWorkerAffinity(cpu int) IsolationStatus { return ApplyPacerIsolation(cpu, false) }
