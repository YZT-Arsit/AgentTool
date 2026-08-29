package main

import (
	"flag"
	"fmt"
	"os"

	gatewayv2 "common-action-gateway-v2"
)

func main() {
	listen := flag.String("listen", "127.0.0.1:0", "local listen address")
	name := flag.String("name", "FAST", "provider class")
	minDelay := flag.Int("min-delay-ms", 1, "minimum response delay")
	maxDelay := flag.Int("max-delay-ms", 2, "maximum response delay")
	cpuWork := flag.Int("cpu-work-ms", 0, "per-request CPU work")
	background := flag.Int("background-workers", 0, "background CPU-load workers")
	seed := flag.Int64("seed", 1, "local emulator seed")
	cpu := flag.Int("cpu", -1, "emulator CPU affinity")
	effectful := flag.Bool("effectful", false, "perform one idempotent synthetic effect per operation ID")
	flag.Parse()
	err := gatewayv2.RunProviderEmulator(gatewayv2.EmulatorConfig{Listen: *listen, Name: *name,
		MinDelayMS: *minDelay, MaxDelayMS: *maxDelay, CPUWorkMS: *cpuWork,
		BackgroundWorkers: *background, Seed: *seed, CPU: *cpu, Effectful: *effectful},
		func(address string) { fmt.Printf("READY http://%s/execute pid=%d\n", address, os.Getpid()) })
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
