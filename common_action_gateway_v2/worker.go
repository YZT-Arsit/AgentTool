package gatewayv2

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

type WorkerConfig struct {
	RequestRingPath string
	ResultRingPath  string
	RingCapacity    int
	FrameBytes      int
	ExpectedFrames  int
	KeyHex          string
	ProviderConfig  string
	PrivateLogPath  string
	CPU             int
	Ready           func()
}

type WorkerEvent struct {
	OperationID string `json:"operation_id"`
	Session     uint32 `json:"session"`
	Slot        uint32 `json:"slot"`
	Action      byte   `json:"action"`
	Provider    byte   `json:"provider"`
	StartedNS   int64  `json:"started_ns"`
	CompletedNS int64  `json:"completed_ns"`
	Status      byte   `json:"status"`
	Effect      bool   `json:"effect"`
}

func RunWorker(config WorkerConfig) (IsolationStatus, error) {
	status := ApplyWorkerAffinity(config.CPU)
	requestRing, err := CreateRing(config.RequestRingPath, config.RingCapacity, config.FrameBytes)
	if err != nil {
		return status, err
	}
	defer requestRing.Close()
	resultRing, err := CreateRing(config.ResultRingPath, config.RingCapacity, InternalResultBytes)
	if err != nil {
		return status, err
	}
	defer resultRing.Close()
	aead, err := ParseKey(config.KeyHex)
	if err != nil {
		return status, err
	}
	providerConfig, err := LoadProviderConfig(config.ProviderConfig)
	if err != nil {
		return status, err
	}
	var adapter ProviderAdapter
	if providerConfig.AllowGenericHTTP {
		adapter, err = NewGenericHTTPProviderAdapter(providerConfig)
	} else {
		adapter, err = NewLocalProviderAdapter(providerConfig)
	}
	if err != nil {
		return status, err
	}
	if config.Ready != nil {
		config.Ready()
	}

	frame := make([]byte, config.FrameBytes)
	completion := make(chan ResultRecord, config.RingCapacity)
	events := make([]WorkerEvent, 0, config.ExpectedFrames)
	var eventMu sync.Mutex
	var outstanding atomic.Int64
	var processed int
	var resultDrops atomic.Int64
	seen := make(map[[OperationIDBytes]byte]bool)
	var seenMu sync.Mutex

	writerDone := make(chan struct{})
	go func() {
		buffer := make([]byte, InternalResultBytes)
		for result := range completion {
			MarshalResult(buffer, result)
			for !resultRing.TryPush(buffer) {
				resultDrops.Add(1)
				runtime.Gosched()
			}
		}
		close(writerDone)
	}()

	for processed < config.ExpectedFrames {
		if !requestRing.TryPop(frame) {
			time.Sleep(100 * time.Microsecond)
			continue
		}
		processed++
		op, err := DecodeRequest(aead, frame)
		if err != nil {
			continue
		}
		if op.Action == ActionNoop {
			continue
		}
		seenMu.Lock()
		duplicate := seen[op.OperationID]
		if !duplicate {
			seen[op.OperationID] = true
		}
		seenMu.Unlock()
		if duplicate {
			continue
		}
		outstanding.Add(1)
		go func(operation PrivateOperation) {
			started := MonotonicNowNS()
			var result ResultRecord
			if operation.Action == ActionAgent {
				result = baseResult(operation)
				result.Status = StatusOK
			} else {
				ctx, cancel := context.WithTimeout(context.Background(), time.Duration(providerConfig.TimeoutMS)*time.Millisecond)
				result = adapter.Execute(ctx, operation)
				cancel()
			}
			completed := MonotonicNowNS()
			completion <- result
			eventMu.Lock()
			events = append(events, WorkerEvent{OperationID: OperationIDString(operation.OperationID),
				Session: operation.Session, Slot: operation.Slot, Action: operation.Action,
				Provider: operation.Provider, StartedNS: started, CompletedNS: completed,
				Status: result.Status, Effect: operation.Action == ActionTool && result.Status == StatusOK})
			eventMu.Unlock()
			outstanding.Add(-1)
		}(op)
	}
	for outstanding.Load() != 0 {
		time.Sleep(time.Millisecond)
	}
	close(completion)
	<-writerDone

	file, err := os.Create(config.PrivateLogPath)
	if err != nil {
		return status, err
	}
	encoder := json.NewEncoder(file)
	for _, event := range events {
		if err := encoder.Encode(event); err != nil {
			file.Close()
			return status, err
		}
	}
	summary := map[string]any{"kind": "SUMMARY", "processed_frames": processed,
		"real_operations": len(events), "dummy_heavy_ops": 0, "result_ring_waits": resultDrops.Load(),
		"pid": os.Getpid(), "isolation": status}
	if err := encoder.Encode(summary); err != nil {
		file.Close()
		return status, err
	}
	if err := file.Close(); err != nil {
		return status, err
	}
	if processed != config.ExpectedFrames {
		return status, fmt.Errorf("processed %d frames, expected %d", processed, config.ExpectedFrames)
	}
	return status, nil
}
