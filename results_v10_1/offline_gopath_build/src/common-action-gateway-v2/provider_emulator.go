package gatewayv2

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"net"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

type EmulatorConfig struct {
	Listen            string
	Name              string
	MinDelayMS        int
	MaxDelayMS        int
	CPUWorkMS         int
	BackgroundWorkers int
	Seed              int64
	CPU               int
	Effectful         bool
}

type modelTool struct {
	Name   string `json:"name"`
	Handle int    `json:"handle"`
}

type modelContextItem struct {
	Role    string `json:"role"`
	Content string `json:"content,omitempty"`
}

type modelRequest struct {
	Context []modelContextItem `json:"context"`
	Tools   []modelTool        `json:"tools"`
}

func localModelDecision(operationID string, payload []byte) []byte {
	var request modelRequest
	if json.Unmarshal(payload, &request) != nil {
		encoded, _ := json.Marshal(map[string]any{"kind": "ERROR", "error": "INVALID_MODEL_REQUEST"})
		return encoded
	}
	for _, item := range request.Context {
		if item.Role == "tool" {
			encoded, _ := json.Marshal(map[string]any{"kind": "FINAL", "text": "completed:" + item.Content})
			return encoded
		}
	}
	if len(request.Tools) > 0 {
		encoded, _ := json.Marshal(map[string]any{
			"kind": "TOOL_CALL", "name": request.Tools[0].Name,
			"arguments": map[string]any{"topic": "synthetic-local"},
			"call_id": "call-" + operationID,
		})
		return encoded
	}
	encoded, _ := json.Marshal(map[string]any{"kind": "FINAL", "text": "completed:no-tool"})
	return encoded
}

func burnCPU(duration time.Duration) {
	deadline := time.Now().Add(duration)
	var value uint64 = 1
	for time.Now().Before(deadline) {
		value = value*1664525 + 1013904223
	}
	_ = value
}

func RunProviderEmulator(config EmulatorConfig, ready func(string)) error {
	_ = ApplyWorkerAffinity(config.CPU)
	listener, err := net.Listen("tcp", config.Listen)
	if err != nil {
		return err
	}
	defer listener.Close()
	stopLoad := make(chan struct{})
	for i := 0; i < config.BackgroundWorkers; i++ {
		go func() {
			for {
				select {
				case <-stopLoad:
					return
				default:
					burnCPU(5 * time.Millisecond)
					time.Sleep(time.Millisecond)
				}
			}
		}()
	}
	defer close(stopLoad)
	rng := rand.New(rand.NewSource(config.Seed))
	var rngMu sync.Mutex
	seen := make(map[string]providerResponse)
	var seenMu sync.Mutex
	var effects atomic.Int64
	handler := http.NewServeMux()
	handler.HandleFunc("/execute", func(writer http.ResponseWriter, request *http.Request) {
		defer request.Body.Close()
		var input providerRequest
		if err := json.NewDecoder(request.Body).Decode(&input); err != nil {
			http.Error(writer, "invalid", http.StatusBadRequest)
			return
		}
		seenMu.Lock()
		cached, duplicate := seen[input.OperationID]
		seenMu.Unlock()
		if duplicate {
			writer.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(writer).Encode(cached)
			return
		}
		delay := config.MinDelayMS
		if config.MaxDelayMS > config.MinDelayMS {
			rngMu.Lock()
			delay += rng.Intn(config.MaxDelayMS - config.MinDelayMS + 1)
			rngMu.Unlock()
		}
		if config.CPUWorkMS > 0 {
			burnCPU(time.Duration(config.CPUWorkMS) * time.Millisecond)
		}
		time.Sleep(time.Duration(delay) * time.Millisecond)
		count := effects.Load()
		if config.Effectful {
			count = effects.Add(1)
		}
		payload := []byte(fmt.Sprintf("%s:%d", config.Name, count))
		if config.Name == "LOCAL_MODEL" {
			payload = localModelDecision(input.OperationID, input.Payload)
		}
		response := providerResponse{Status: "OK", Payload: payload}
		seenMu.Lock()
		seen[input.OperationID] = response
		seenMu.Unlock()
		writer.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(writer).Encode(response)
	})
	server := &http.Server{Handler: handler, ReadHeaderTimeout: 2 * time.Second}
	ready(listener.Addr().String())
	err = server.Serve(listener)
	if err == http.ErrServerClosed {
		return nil
	}
	return err
}
