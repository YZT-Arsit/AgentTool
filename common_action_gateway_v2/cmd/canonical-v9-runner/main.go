package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"common-action-gateway-v2/canonicalv9"
)

func main() {
	planPath := flag.String("plan", "", "trusted canonical session plan JSON")
	outputPath := flag.String("output", "", "private canonical result JSON")
	diagnostics := flag.Bool("diagnostics", false, "run canonical wire-size and admission diagnostics")
	recoveryMatrix := flag.Bool("recovery-matrix", false, "run canonical durable recovery matrix")
	online := flag.Bool("online", false, "run one trusted-control online canonical session")
	flag.Parse()
	if *planPath == "" || *outputPath == "" {
		fmt.Fprintln(os.Stderr, "--plan and --output are required")
		os.Exit(2)
	}
	raw, err := os.ReadFile(*planPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var plan canonicalv9.Plan
	if err := json.Unmarshal(raw, &plan); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var result any
	if *recoveryMatrix {
		result, err = canonicalv9.RecoveryMatrix(plan.StateDirectory+"-recovery-matrix", plan.MaximumRealOperations+1)
	} else if *diagnostics {
		result, err = canonicalv9.Diagnostics(plan)
	} else if *online {
		result, err = canonicalv9.RunOnline(plan, os.Stdin, os.Stdout)
	} else {
		result, err = canonicalv9.Run(plan)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoded, _ := json.MarshalIndent(result, "", "  ")
	if err := os.WriteFile(*outputPath, append(encoded, '\n'), 0o600); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
