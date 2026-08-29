package main

import (
	"flag"
	"fmt"
	"os"

	gatewayv2 "common-action-gateway-v2"
	"common-action-gateway-v2/v7"
)

func main() {
	listen := flag.String("listen", "127.0.0.1:0", "public tunnel listen address")
	wireProfilePath := flag.String("profile", "", "public wire profile JSON")
	admissionPath := flag.String("admission-profile", "", "public V7 admission profile JSON")
	requestRing := flag.String("request-ring", "", "request ring path")
	resultRing := flag.String("result-ring", "", "result ring path")
	readyQueue := flag.String("ready-queue", "", "durable private ready queue")
	workerDone := flag.String("worker-done", "", "private worker completion marker")
	key := flag.String("key", "", "ephemeral experiment key")
	keyFile := flag.String("key-file", "", "restricted local key file")
	hostLog := flag.String("host-log", "pacer_host_v7.jsonl", "post-session host timing log")
	privateLog := flag.String("private-log", "pacer_private_v7.jsonl", "post-session private delivery log")
	lifecycle := flag.String("lifecycle", "gateway_lifecycle_v7.csv", "post-session private lifecycle log")
	statusPath := flag.String("status", "pacer_status_v7.json", "functional status")
	cpu := flag.Int("cpu", -1, "pacer CPU affinity")
	realtime := flag.Bool("realtime", false, "request Linux SCHED_FIFO")
	flag.Parse()
	wire, err := gatewayv2.LoadProfile(*wireProfilePath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	admission, err := v7.LoadAdmissionProfile(*admissionPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	err = v7.RunPacer(v7.PacerConfig{Listen: *listen, WireProfile: wire, Admission: admission,
		RequestRingPath: *requestRing, ResultRingPath: *resultRing, ReadyQueuePath: *readyQueue,
		WorkerDonePath: *workerDone, KeyHex: *key, KeyFile: *keyFile, HostLogPath: *hostLog,
		PrivateLogPath: *privateLog, LifecyclePath: *lifecycle, StatusPath: *statusPath,
		CPU: *cpu, Realtime: *realtime}, func(address string) {
		fmt.Printf("READY %s pid=%d\n", address, os.Getpid())
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
