package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	gatewayv2 "common-action-gateway-v2"
)

func main() {
	requestRing := flag.String("request-ring", "", "request shared-memory ring path")
	resultRing := flag.String("result-ring", "", "result shared-memory ring path")
	capacity := flag.Int("capacity", 4096, "ring capacity")
	frameBytes := flag.Int("frame-bytes", 1024, "fixed frame bytes")
	expected := flag.Int("expected-frames", 0, "public request frame count")
	key := flag.String("key", "", "ephemeral experiment key")
	keyFile := flag.String("key-file", "", "restricted local key file")
	profilePath := flag.String("profile", "", "public wire profile JSON")
	providers := flag.String("providers", "", "private provider configuration")
	privateLog := flag.String("private-log", "worker_private_v7.jsonl", "private worker log")
	journal := flag.String("operation-journal", "", "durable trusted operation journal")
	workerDone := flag.String("worker-done", "", "private worker-completion marker")
	cpu := flag.Int("cpu", -1, "worker CPU affinity")
	flag.Parse()
	profile, err := gatewayv2.LoadProfile(*profilePath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	_, err = gatewayv2.RunWorker(gatewayv2.WorkerConfig{
		RequestRingPath: *requestRing, ResultRingPath: *resultRing, RingCapacity: *capacity,
		FrameBytes: *frameBytes, ExpectedFrames: *expected, KeyHex: *key, KeyFile: *keyFile,
		ProfileID: profile.ID(), Sessions: profile.Sessions, Slots: profile.Slots,
		ProviderConfig: *providers, PrivateLogPath: *privateLog, JournalPath: *journal, CPU: *cpu,
		Ready: func() { fmt.Printf("READY pid=%d\n", os.Getpid()) },
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if *workerDone != "" {
		marker, _ := json.Marshal(map[string]any{"worker_complete": true, "monotonic_ns": gatewayv2.MonotonicNowNS(),
			"wall_clock_utc": time.Now().UTC().Format(time.RFC3339Nano)})
		if err := os.WriteFile(*workerDone, marker, 0o600); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
}
