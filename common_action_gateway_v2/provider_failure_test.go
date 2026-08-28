package gatewayv2

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func localAdapterForTest(t *testing.T, server *httptest.Server, timeoutMS int, effectful bool) *HTTPProviderAdapter {
	t.Helper()
	adapter, err := NewHTTPProviderAdapter(ProviderConfig{
		Endpoints: map[string]string{"EFFECTFUL_TOOL": server.URL},
		Effectful: map[string]bool{"EFFECTFUL_TOOL": effectful},
		TimeoutMS: timeoutMS,
	})
	if err != nil {
		t.Fatal(err)
	}
	return adapter
}

func effectOperation(id string) PrivateOperation {
	return PrivateOperation{Action: ActionTool, Provider: ProviderEffectful,
		OperationID: OperationID(id), Session: 0, Slot: 1}
}

func writeProviderOK(writer http.ResponseWriter, payload string) {
	writer.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(writer).Encode(providerResponse{Status: "OK", Payload: []byte(payload)})
}

func TestProviderTimeoutBeforeEffectRecordsNoEffect(t *testing.T) {
	var effects atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		select {
		case <-time.After(80 * time.Millisecond):
			effects.Add(1)
			writeProviderOK(writer, "late")
		case <-request.Context().Done():
			return
		}
	}))
	defer server.Close()
	result := localAdapterForTest(t, server, 15, true).Execute(context.Background(), effectOperation("before-effect"))
	if result.Status != StatusTimeout || effects.Load() != 0 {
		t.Fatalf("status=%d effects=%d", result.Status, effects.Load())
	}
}

func TestProviderTimeoutAfterEffectIsExplicitlyAmbiguous(t *testing.T) {
	var effects atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		effects.Add(1)
		time.Sleep(80 * time.Millisecond)
		writeProviderOK(writer, "effect-committed")
	}))
	defer server.Close()
	result := localAdapterForTest(t, server, 15, true).Execute(context.Background(), effectOperation("after-effect"))
	if result.Status != StatusTimeout || effects.Load() != 1 {
		t.Fatalf("timeout after an irreversible effect must remain visible as ambiguous: status=%d effects=%d",
			result.Status, effects.Load())
	}
}

func TestProviderDuplicateOperationIDCanReturnCachedResultExactlyOnce(t *testing.T) {
	var effects atomic.Int64
	cache := map[string]providerResponse{}
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		var input providerRequest
		_ = json.NewDecoder(request.Body).Decode(&input)
		response, ok := cache[input.OperationID]
		if !ok {
			effects.Add(1)
			response = providerResponse{Status: "OK", Payload: []byte("once")}
			cache[input.OperationID] = response
		}
		_ = json.NewEncoder(writer).Encode(response)
	}))
	defer server.Close()
	adapter := localAdapterForTest(t, server, 500, true)
	first := adapter.Execute(context.Background(), effectOperation("same-id"))
	second := adapter.Execute(context.Background(), effectOperation("same-id"))
	if first.Status != StatusOK || second.Status != StatusOK || effects.Load() != 1 {
		t.Fatalf("duplicate was not idempotent: first=%d second=%d effects=%d",
			first.Status, second.Status, effects.Load())
	}
}

func TestProviderErrorAndConnectionInterruptionMapToPrivateError(t *testing.T) {
	errorServer := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		http.Error(writer, "synthetic", http.StatusInternalServerError)
	}))
	errorResult := localAdapterForTest(t, errorServer, 500, false).Execute(
		context.Background(), effectOperation("provider-error"))
	errorServer.Close()
	if errorResult.Status != StatusError {
		t.Fatalf("provider error status=%d", errorResult.Status)
	}

	interruptServer := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		connection, _, err := writer.(http.Hijacker).Hijack()
		if err == nil {
			_ = connection.Close()
		}
	}))
	interruptResult := localAdapterForTest(t, interruptServer, 500, false).Execute(
		context.Background(), effectOperation("connection-interruption"))
	interruptServer.Close()
	if interruptResult.Status != StatusError {
		t.Fatalf("connection interruption status=%d", interruptResult.Status)
	}
}
