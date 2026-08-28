package main

import (
	"flag"
	"fmt"
	"os"

	gatewayv2 "common-action-gateway-v2"
)

func main() {
	requestRing := flag.String("request-ring", "", "request shared-memory ring path")
	resultRing := flag.String("result-ring", "", "result shared-memory ring path")
	capacity := flag.Int("capacity", 4096, "ring capacity")
	frameBytes := flag.Int("frame-bytes", 1024, "fixed frame bytes")
	expected := flag.Int("expected-frames", 0, "public request frame count")
	key := flag.String("key", "", "ephemeral experiment key")
	providers := flag.String("providers", "", "private provider configuration")
	privateLog := flag.String("private-log", "worker_private.jsonl", "private worker log")
	cpu := flag.Int("cpu", -1, "worker CPU affinity")
	flag.Parse()
	_, err := gatewayv2.RunWorker(gatewayv2.WorkerConfig{
		RequestRingPath: *requestRing, ResultRingPath: *resultRing, RingCapacity: *capacity,
		FrameBytes: *frameBytes, ExpectedFrames: *expected, KeyHex: *key,
		ProviderConfig: *providers, PrivateLogPath: *privateLog, CPU: *cpu,
		Ready: func() { fmt.Printf("READY pid=%d\n", os.Getpid()) },
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
