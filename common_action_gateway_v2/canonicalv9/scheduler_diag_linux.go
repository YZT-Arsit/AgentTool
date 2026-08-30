//go:build linux

package canonicalv9

import (
	"os"
	"runtime"
	"strconv"
	"strings"
	"syscall"
)

func parseUint(value string) uint64 {
	parsed, _ := strconv.ParseUint(value, 10, 64)
	return parsed
}

func schedulerHostSnapshot() SchedulerHostSnapshot {
	var memory runtime.MemStats
	runtime.ReadMemStats(&memory)
	tid := syscall.Gettid()
	result := SchedulerHostSnapshot{
		PID:            os.Getpid(),
		TID:            tid,
		CPU:            -1,
		GOMAXPROCS:     runtime.GOMAXPROCS(0),
		GCCycles:       memory.NumGC,
		GCPauseTotalNS: memory.PauseTotalNs,
	}
	statusPath := "/proc/self/task/" + strconv.Itoa(tid) + "/status"
	if raw, err := os.ReadFile(statusPath); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			fields := strings.Fields(line)
			if len(fields) < 2 {
				continue
			}
			switch strings.TrimSuffix(fields[0], ":") {
			case "Cpus_allowed_list":
				result.CPUAffinity = fields[1]
			case "voluntary_ctxt_switches":
				result.VoluntaryContextSwitches = parseUint(fields[1])
			case "nonvoluntary_ctxt_switches":
				result.NonvoluntaryContextSwitches = parseUint(fields[1])
			}
		}
	} else {
		result.Unavailable = append(result.Unavailable, "task_status")
	}
	if raw, err := os.ReadFile("/proc/self/task/" + strconv.Itoa(tid) + "/stat"); err == nil {
		closeParen := strings.LastIndexByte(string(raw), ')')
		if closeParen >= 0 {
			fields := strings.Fields(string(raw)[closeParen+1:])
			if len(fields) > 36 {
				result.CPU = int(parseUint(fields[36]))
			}
		}
	} else {
		result.Unavailable = append(result.Unavailable, "task_stat")
	}
	if raw, err := os.ReadFile("/proc/self/stat"); err == nil {
		closeParen := strings.LastIndexByte(string(raw), ')')
		if closeParen >= 0 {
			fields := strings.Fields(string(raw)[closeParen+1:])
			if len(fields) > 12 {
				result.ProcessCPUTimeTicks = parseUint(fields[11]) + parseUint(fields[12])
			}
		}
	} else {
		result.Unavailable = append(result.Unavailable, "process_stat")
	}
	if raw, err := os.ReadFile("/proc/pressure/cpu"); err == nil {
		result.CPUPressure = strings.TrimSpace(string(raw))
	} else {
		result.Unavailable = append(result.Unavailable, "cpu_pressure")
	}
	if raw, err := os.ReadFile("/sys/fs/cgroup/cpu.stat"); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			fields := strings.Fields(line)
			if len(fields) != 2 {
				continue
			}
			switch fields[0] {
			case "nr_throttled":
				result.CgroupNRThrottled = parseUint(fields[1])
			case "throttled_usec":
				result.CgroupThrottledUsec = parseUint(fields[1])
			}
		}
	} else {
		result.Unavailable = append(result.Unavailable, "cgroup_cpu_stat")
	}
	if values, err := os.ReadFile("/proc/loadavg"); err == nil {
		fields := strings.Fields(string(values))
		for index := 0; index < 3 && index < len(fields); index++ {
			result.LoadAverage[index], _ = strconv.ParseFloat(fields[index], 64)
		}
	} else {
		result.Unavailable = append(result.Unavailable, "load_average")
	}
	return result
}
