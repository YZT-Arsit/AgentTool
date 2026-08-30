//go:build linux

package canonicalv9

import (
	"errors"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	linuxClockMonotonic = 1
	linuxTimerAbsTime   = 1
	affinityBytes       = 128
)

type linuxAbsolutePacer struct {
	baseGo     time.Time
	baseKernel syscall.Timespec
	config     SchedulerConfiguration
}

func rawClockGettime() (syscall.Timespec, error) {
	var value syscall.Timespec
	_, _, errno := syscall.RawSyscall(
		syscall.SYS_CLOCK_GETTIME,
		linuxClockMonotonic,
		uintptr(unsafe.Pointer(&value)),
		0,
	)
	if errno != 0 {
		return syscall.Timespec{}, errno
	}
	return value, nil
}

func addDuration(value syscall.Timespec, duration time.Duration) syscall.Timespec {
	seconds := int64(duration / time.Second)
	nanoseconds := int64(duration % time.Second)
	value.Sec += seconds
	value.Nsec += nanoseconds
	if value.Nsec >= int64(time.Second) {
		value.Sec++
		value.Nsec -= int64(time.Second)
	} else if value.Nsec < 0 {
		value.Sec--
		value.Nsec += int64(time.Second)
	}
	return value
}

func schedSetAffinity(tid, cpu int) error {
	if cpu < 0 || cpu >= affinityBytes*8 {
		return fmt.Errorf("pacer CPU %d is outside affinity mask capacity", cpu)
	}
	mask := make([]byte, affinityBytes)
	mask[cpu/8] |= byte(1 << uint(cpu%8))
	_, _, errno := syscall.RawSyscall(
		syscall.SYS_SCHED_SETAFFINITY,
		uintptr(tid),
		uintptr(len(mask)),
		uintptr(unsafe.Pointer(&mask[0])),
	)
	if errno != 0 {
		return errno
	}
	return nil
}

func affinityListFromStatus(path string) string {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(raw), "\n") {
		fields := strings.Fields(line)
		if len(fields) >= 2 && strings.TrimSuffix(fields[0], ":") == "Cpus_allowed_list" {
			return fields[1]
		}
	}
	return ""
}

func affinityListExcludesCPU(list string, cpu int) bool {
	if list == "" {
		return false
	}
	for _, section := range strings.Split(list, ",") {
		bounds := strings.SplitN(section, "-", 2)
		start, err := strconv.Atoi(bounds[0])
		if err != nil {
			continue
		}
		end := start
		if len(bounds) == 2 {
			end, _ = strconv.Atoi(bounds[1])
		}
		if cpu >= start && cpu <= end {
			return false
		}
	}
	return true
}

func newPublicPacer() (publicPacer, error) {
	runtime.LockOSThread()
	baseGo := time.Now()
	baseKernel, err := rawClockGettime()
	if err != nil {
		runtime.UnlockOSThread()
		return nil, err
	}
	tid := syscall.Gettid()
	config := SchedulerConfiguration{
		Implementation:       "LINUX_CLOCK_NANOSLEEP_TIMER_ABSTIME",
		Clock:                "CLOCK_MONOTONIC",
		AbsoluteDeadlines:    true,
		OSThreadLocked:       true,
		PacerTID:             tid,
		PacerCPU:             -1,
		FrameworkProcessCPUs: affinityListFromStatus("/proc/self/status"),
	}
	if requested := os.Getenv("AGENTTOOL_PACER_CPU"); requested != "" {
		config.AffinityRequested = true
		cpu, parseErr := strconv.Atoi(requested)
		if parseErr != nil {
			config.AffinityError = parseErr.Error()
		} else if affinityErr := schedSetAffinity(tid, cpu); affinityErr != nil {
			config.AffinityError = affinityErr.Error()
		} else {
			config.PacerCPU = cpu
			config.PacerAffinity = affinityListFromStatus(
				"/proc/self/task/" + strconv.Itoa(tid) + "/status",
			)
			config.AffinitySucceeded = config.PacerAffinity == strconv.Itoa(cpu)
			config.IsolationVerified = config.AffinitySucceeded && affinityListExcludesCPU(config.FrameworkProcessCPUs, cpu)
			if !config.IsolationVerified && config.AffinityError == "" {
				config.AffinityError = "framework process affinity includes pacer CPU"
			}
		}
	}
	return &linuxAbsolutePacer{baseGo: baseGo, baseKernel: baseKernel, config: config}, nil
}

func (pacer *linuxAbsolutePacer) WaitUntil(deadline time.Time) error {
	target := addDuration(pacer.baseKernel, deadline.Sub(pacer.baseGo))
	for {
		_, _, errno := syscall.RawSyscall6(
			syscall.SYS_CLOCK_NANOSLEEP,
			linuxClockMonotonic,
			linuxTimerAbsTime,
			uintptr(unsafe.Pointer(&target)),
			0,
			0,
			0,
		)
		if errno == 0 {
			return nil
		}
		if errors.Is(errno, syscall.EINTR) {
			continue
		}
		return errno
	}
}

func (pacer *linuxAbsolutePacer) Close() SchedulerConfiguration {
	runtime.UnlockOSThread()
	return pacer.config
}
