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
	key := flag.String("key", "", "ephemeral experiment key")
	hostLog := flag.String("host-log", "cloud_host.jsonl", "post-session cloud timing log")
	cpu := flag.Int("cpu", -1, "cloud client CPU affinity")
	flag.Parse()
	profile, err := gatewayv2.LoadProfile(*profilePath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	workload, err := gatewayv2.LoadWorkload(*workloadPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := gatewayv2.RunCloudClient(gatewayv2.ClientConfig{Address: *address, Profile: profile,
		Workload: workload, KeyHex: *key, HostLogPath: *hostLog, CPU: *cpu}); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
