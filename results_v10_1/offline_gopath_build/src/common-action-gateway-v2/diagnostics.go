package gatewayv2

import (
	"bufio"
	"encoding/json"
	"os"
)

type IsolationStatus struct {
	Platform                string `json:"platform"`
	ReferenceTimingPlatform bool   `json:"reference_timing_platform"`
	RequestedCPU            int    `json:"requested_cpu"`
	AffinityApplied         bool   `json:"affinity_applied"`
	AffinityDetail          string `json:"affinity_detail"`
	RealtimeRequested       bool   `json:"realtime_requested"`
	RealtimeApplied         bool   `json:"realtime_applied"`
	RealtimeDetail          string `json:"realtime_detail"`
	Note                    string `json:"note,omitempty"`
}

type TimingEvent struct {
	Direction       string `json:"direction"`
	Session         uint32 `json:"session"`
	Slot            uint32 `json:"slot"`
	ScheduledNS     int64  `json:"scheduled_send_ns"`
	CutoffNS        int64  `json:"preparation_cutoff_ns,omitempty"`
	PreparedNS      int64  `json:"prepared_ns,omitempty"`
	ActualSendNS    int64  `json:"actual_socket_send_ns,omitempty"`
	ActualReceiveNS int64  `json:"actual_socket_receive_ns,omitempty"`
	FrameBytes      int    `json:"frame_bytes"`
	Destination     string `json:"destination"`
}

type DiagnosticRing struct {
	events []TimingEvent
	next   int
}

func NewDiagnosticRing(capacity int) *DiagnosticRing {
	return &DiagnosticRing{events: make([]TimingEvent, capacity)}
}

func (r *DiagnosticRing) Append(event TimingEvent) {
	if r.next >= len(r.events) {
		return
	}
	r.events[r.next] = event
	r.next++
}

func (r *DiagnosticRing) Events() []TimingEvent { return r.events[:r.next] }

func DumpJSONL(path string, collections ...[]TimingEvent) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	writer := bufio.NewWriter(file)
	encoder := json.NewEncoder(writer)
	for _, events := range collections {
		for _, event := range events {
			if err := encoder.Encode(event); err != nil {
				return err
			}
		}
	}
	return writer.Flush()
}
