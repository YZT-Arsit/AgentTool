//go:build v12_provider_measurement

package canonicalv9

import (
	"encoding/json"
	"net/http"
	"os"
	"sort"
	"strconv"
	"sync"
	"testing"
	"time"

	gatewayv2 "common-action-gateway-v2"
)

type providerMeasurementEntry struct {
	Session     int    `json:"session"`
	Attempt     int    `json:"attempt"`
	Identity    string `json:"identity"`
	OperationID string `json:"operation_id"`
}

type providerMeasurementFreeze struct {
	MeasurementSessions               int                        `json:"measurement_sessions"`
	AttemptsPerSession                int                        `json:"attempts_per_session"`
	TotalAttempts                     int                        `json:"total_attempts"`
	MaximumSupportedActionConcurrency int                        `json:"maximum_supported_action_concurrency"`
	Attempts                          []providerMeasurementEntry `json:"attempts"`
}

type providerMeasurementResult struct {
	providerMeasurementEntry
	Status     byte               `json:"status"`
	Diagnostic ProviderDiagnostic `json:"diagnostic"`
}

func TestV12ProviderBoundMeasurement(t *testing.T) {
	manifestPath := os.Getenv("V12_PROVIDER_MEASUREMENT_MANIFEST")
	outputPath := os.Getenv("V12_PROVIDER_MEASUREMENT_OUTPUT")
	endpoint := os.Getenv("V12_PROVIDER_MEASUREMENT_ENDPOINT")
	timeoutMS, err := strconv.Atoi(os.Getenv("V12_PROVIDER_MEASUREMENT_TIMEOUT_MS"))
	if err != nil || timeoutMS <= 0 || manifestPath == "" || outputPath == "" || endpoint == "" {
		t.Fatal("provider measurement environment is incomplete")
	}
	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatal(err)
	}
	var freeze providerMeasurementFreeze
	if err := json.Unmarshal(raw, &freeze); err != nil {
		t.Fatal(err)
	}
	if freeze.MeasurementSessions != 200 || freeze.AttemptsPerSession != 50 ||
		freeze.MaximumSupportedActionConcurrency != 50 || freeze.TotalAttempts != 10000 ||
		len(freeze.Attempts) != freeze.TotalAttempts {
		t.Fatalf("provider measurement freeze is malformed: %+v", freeze)
	}
	bySession := make(map[int][]providerMeasurementEntry)
	seen := make(map[string]bool)
	for _, entry := range freeze.Attempts {
		if entry.Session < 1 || entry.Session > freeze.MeasurementSessions ||
			entry.Attempt < 1 || entry.Attempt > freeze.AttemptsPerSession ||
			entry.Identity == "" || entry.OperationID == "" || seen[entry.OperationID] {
			t.Fatalf("invalid or duplicate measurement entry: %+v", entry)
		}
		seen[entry.OperationID] = true
		bySession[entry.Session] = append(bySession[entry.Session], entry)
	}
	results := make([]providerMeasurementResult, 0, freeze.TotalAttempts)
	for session := 1; session <= freeze.MeasurementSessions; session++ {
		entries := bySession[session]
		if len(entries) != freeze.AttemptsPerSession {
			t.Fatalf("session %d has %d attempts", session, len(entries))
		}
		current := &engine{
			plan:       Plan{ProviderCompletionBoundMS: timeoutMS},
			httpClient: &http.Client{Timeout: time.Duration(timeoutMS) * time.Millisecond},
			started:    time.Now(),
		}
		start := make(chan struct{})
		batch := make(chan providerMeasurementResult, len(entries))
		var wait sync.WaitGroup
		for _, entry := range entries {
			entry := entry
			wait.Add(1)
			go func() {
				defer wait.Done()
				<-start
				attempt := current.callProvider(
					RouteSpec{RouteHandle: "route-tool-read", Endpoint: endpoint},
					entry.OperationID,
					[]byte(`{"arguments":{"city":"Paris"}}`),
				)
				batch <- providerMeasurementResult{entry, attempt.status, attempt.diagnostic}
			}()
		}
		close(start)
		wait.Wait()
		close(batch)
		for result := range batch {
			if result.Status != gatewayv2.StatusOK || result.Diagnostic.Class != ProviderOK {
				t.Fatalf("measurement attempt failed: %+v", result)
			}
			results = append(results, result)
		}
	}
	sort.Slice(results, func(i, j int) bool {
		if results[i].Session != results[j].Session {
			return results[i].Session < results[j].Session
		}
		return results[i].Attempt < results[j].Attempt
	})
	encoded, err := json.MarshalIndent(map[string]any{
		"schema":  "AgentTool.V12V4R7ProviderPathMeasurementRaw/1",
		"results": results,
	}, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(outputPath, append(encoded, '\n'), 0o600); err != nil {
		t.Fatal(err)
	}
}
