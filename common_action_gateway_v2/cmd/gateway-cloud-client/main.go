package main

import (
	"flag"
	"fmt"
	"os"

	gatewayv2 "common-action-gateway-v2"
)

func main() {
	address := flag.String("address", "", "Gateway Pacer address")
	profilePath := flag.String("profile", "", "public profile JSON")
	workloadPath := flag.String("workload", "", "private local workload JSON")
	framesPath := flag.String("opaque-frames", "", "pre-encrypted fixed frames; cloud client receives no key")
	responsesPath := flag.String("opaque-responses", "", "write opaque response frames for trusted consumer")
	key := flag.String("key", "", "ephemeral experiment key")
	hostLog := flag.String("host-log", "cloud_host.jsonl", "post-session cloud timing log")
	cpu := flag.Int("cpu", -1, "cloud client CPU affinity")
	flag.Parse()
	profile, err := gatewayv2.LoadProfile(*profilePath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var workload gatewayv2.PrivateWorkload
	var frames [][]byte
	if *framesPath != "" {
		raw, readErr := os.ReadFile(*framesPath)
		if readErr != nil {
			fmt.Fprintln(os.Stderr, readErr)
			os.Exit(1)
		}
		total := profile.Sessions * profile.Slots
		if len(raw) != total*profile.FrameBytes {
			fmt.Fprintln(os.Stderr, "opaque frame file size mismatch")
			os.Exit(1)
		}
		frames = make([][]byte, total)
		for i := 0; i < total; i++ {
			frames[i] = raw[i*profile.FrameBytes : (i+1)*profile.FrameBytes]
		}
	} else {
		workload, err = gatewayv2.LoadWorkload(*workloadPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	if err := gatewayv2.RunCloudClient(gatewayv2.ClientConfig{Address: *address, Profile: profile,
		Workload: workload, Frames: frames, KeyHex: *key, HostLogPath: *hostLog,
		OpaqueResponsesPath: *responsesPath, CPU: *cpu}); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
