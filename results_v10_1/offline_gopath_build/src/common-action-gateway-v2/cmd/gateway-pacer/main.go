package main

import (
	"flag"
	"fmt"
	"os"

	gatewayv2 "common-action-gateway-v2"
)

func main() {
	listen := flag.String("listen", "127.0.0.1:0", "public tunnel listen address")
	profilePath := flag.String("profile", "", "public profile JSON")
	requestRing := flag.String("request-ring", "", "request ring path")
	resultRing := flag.String("result-ring", "", "result ring path")
	key := flag.String("key", "", "ephemeral experiment key")
	keyFile := flag.String("key-file", "", "restricted local key file (canonical path)")
	hostLog := flag.String("host-log", "pacer_host.jsonl", "post-session host timing log")
	privateLog := flag.String("private-log", "pacer_private.jsonl", "post-session private delivery log")
	statusPath := flag.String("status", "pacer_status.json", "isolation/capability status")
	cpu := flag.Int("cpu", -1, "pacer CPU affinity")
	realtime := flag.Bool("realtime", false, "request Linux SCHED_FIFO")
	flag.Parse()
	profile, err := gatewayv2.LoadProfile(*profilePath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	err = gatewayv2.RunPacer(gatewayv2.PacerConfig{Listen: *listen, Profile: profile,
		RequestRingPath: *requestRing, ResultRingPath: *resultRing, KeyHex: *key, KeyFile: *keyFile,
		HostLogPath: *hostLog, PrivateLogPath: *privateLog, StatusPath: *statusPath,
		CPU: *cpu, Realtime: *realtime}, func(address string) { fmt.Printf("READY %s pid=%d\n", address, os.Getpid()) })
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
