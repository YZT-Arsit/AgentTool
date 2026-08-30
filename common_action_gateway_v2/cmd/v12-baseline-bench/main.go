// Command v12-baseline-bench is a development-only RFC 9292/RFC 9458
// microbenchmark. It never participates in the canonical or confirmatory path.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"

	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v9ohttp"
	ohttp "github.com/chris-wood/ohttp-go"
)

func main() {
	mode := flag.String("mode", "B2", "B2 unshaped or B3 padded")
	count := flag.Int("count", 1, "real operations")
	argumentBytes := flag.Int("argument-bytes", 24, "private argument bytes")
	resultBytes := flag.Int("result-bytes", 18, "private result bytes")
	flag.Parse()
	// B2 uses a content-dependent public bucket large enough for the RFC9292
	// canonical encoding, while B3 uses the fixed public buckets.  Thus B2 is
	// valid protocol execution but intentionally exposes the private body size.
	requestBytes, responseBytes := 384+*argumentBytes, 180+*resultBytes
	if *mode == "B3" {
		requestBytes, responseBytes = 1024, 768
	}
	private, err := ohttp.NewConfig(7, 0x0020, 0x0001, 0x0001)
	if err != nil {
		panic(err)
	}
	suite := v9ohttp.PublicSuite{KeyID: 7, KEMID: 0x0020, KDFID: 1, AEADID: 1, ConfigurationEpoch: 3, AuthenticatedSource: "V12_DEV_BENCH"}
	client, err := v9ohttp.NewRFC9458Client(private.Config(), suite)
	if err != nil {
		panic(err)
	}
	gateway, err := v9ohttp.NewRFC9458Gateway(private, suite)
	if err != nil {
		panic(err)
	}
	codec := v9ohttp.RFC9292Codec{}
	providerInvocations, relayRequests, gatewayRequests := 0, 0, 0
	var relayConnections, gatewayConnections int64
	relayExact := true
	var relayRequest []byte
	gatewayServer := httptest.NewUnstartedServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		gatewayRequests++
		wire, readErr := io.ReadAll(request.Body)
		if readErr != nil {
			panic(readErr)
		}
		if !bytes.Equal(wire, relayRequest) {
			relayExact = false
		}
		sessionValue, parseErr := strconv.ParseUint(request.Header.Get("X-V12-Session"), 10, 32)
		if parseErr != nil {
			panic(parseErr)
		}
		slotValue, parseErr := strconv.ParseUint(request.Header.Get("X-V12-Slot"), 10, 32)
		if parseErr != nil {
			panic(parseErr)
		}
		slot := v7ohttp.SlotID{Session: uint32(sessionValue), Slot: uint32(slotValue)}
		plain, serverContext, decapErr := gateway.DecapsulateRequest(slot, wire)
		if decapErr != nil {
			panic(decapErr)
		}
		if _, _, decodeErr := codec.DecodeKnownLengthRequest(plain); decodeErr != nil {
			panic(decodeErr)
		}
		providerInvocations++ // deterministic local provider-emulator operation
		responseInner, encodeErr := codec.EncodeKnownLengthResponse(v7ohttp.PrivateResponse{Status: v9ohttp.StatusResult, OperationID: fmt.Sprintf("dev-%d", slot.Slot-1), Payload: bytes.Repeat([]byte("r"), *resultBytes)}, responseBytes)
		if encodeErr != nil {
			panic(encodeErr)
		}
		responseWire, encapsulateErr := gateway.EncapsulateResponse(serverContext, responseInner)
		if encapsulateErr != nil {
			panic(encapsulateErr)
		}
		writer.Header().Set("Content-Type", v7ohttp.ResponseContentType)
		if written, writeErr := writer.Write(responseWire); writeErr != nil || written != len(responseWire) {
			panic("local Gateway response write failed")
		}
	}))
	gatewayServer.Config.ConnState = func(_ net.Conn, state http.ConnState) {
		if state == http.StateNew {
			atomic.AddInt64(&gatewayConnections, 1)
		}
	}
	gatewayServer.Start()
	defer gatewayServer.Close()
	gatewayClient := &http.Client{}
	relayServer := httptest.NewUnstartedServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		relayRequests++
		body, readErr := io.ReadAll(request.Body)
		if readErr != nil {
			panic(readErr)
		}
		relayRequest = append(relayRequest[:0], body...)
		forward, requestErr := http.NewRequest(http.MethodPost, gatewayServer.URL, bytes.NewReader(body))
		if requestErr != nil {
			panic(requestErr)
		}
		forward.Header.Set("Content-Type", request.Header.Get("Content-Type"))
		forward.Header.Set("X-V12-Session", request.Header.Get("X-V12-Session"))
		forward.Header.Set("X-V12-Slot", request.Header.Get("X-V12-Slot"))
		response, forwardErr := gatewayClient.Do(forward)
		if forwardErr != nil {
			panic(forwardErr)
		}
		defer response.Body.Close()
		responseBody, readResponseErr := io.ReadAll(response.Body)
		if readResponseErr != nil {
			panic(readResponseErr)
		}
		writer.Header().Set("Content-Type", response.Header.Get("Content-Type"))
		if written, writeErr := writer.Write(responseBody); writeErr != nil || written != len(responseBody) {
			panic("local Relay response write failed")
		}
	}))
	relayServer.Config.ConnState = func(_ net.Conn, state http.ConnState) {
		if state == http.StateNew {
			atomic.AddInt64(&relayConnections, 1)
		}
	}
	relayServer.Start()
	defer relayServer.Close()
	cloudClient := &http.Client{}
	started := time.Now()
	sent, received := 0, 0
	for index := 0; index < *count; index++ {
		slot := v7ohttp.SlotID{Session: 1, Slot: uint32(index + 1)}
		message := v7ohttp.PrivateActionMessage{ProtocolVersion: 1, Kind: v7ohttp.ActionRealTool, OperationID: []byte(fmt.Sprintf("dev-%d", index)), RouteHandle: []byte("private-route"), ProtectedArgs: bytes.Repeat([]byte("a"), *argumentBytes), Authorization: []byte("development-policy")}
		inner, err := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, message, requestBytes)
		if err != nil {
			panic(err)
		}
		wire, context, err := client.EncapsulateRequest(slot, inner)
		if err != nil {
			panic(err)
		}
		sent += len(wire)
		outerRequest, err := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(wire))
		if err != nil {
			panic(err)
		}
		outerRequest.Header.Set("Content-Type", v7ohttp.RequestContentType)
		outerRequest.Header.Set("X-V12-Session", "1")
		outerRequest.Header.Set("X-V12-Slot", strconv.Itoa(index+1))
		outerResponse, err := cloudClient.Do(outerRequest)
		if err != nil {
			panic(err)
		}
		responseWire, err := io.ReadAll(outerResponse.Body)
		outerResponse.Body.Close()
		if err != nil {
			panic(err)
		}
		received += len(responseWire)
		if _, err = client.DecapsulateResponse(context, responseWire); err != nil {
			panic(err)
		}
	}
	var usage syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &usage); err != nil {
		panic(err)
	}
	value := map[string]any{"mode": *mode, "real_operations": *count, "elapsed_ns": time.Since(started).Nanoseconds(), "bytes_sent": sent, "bytes_received": received, "peak_rss_bytes": usage.Maxrss * 1024, "relay_requests": relayRequests, "gateway_requests": gatewayRequests, "relay_connections": relayConnections, "gateway_connections": gatewayConnections, "relay_endpoint_class": "LOOPBACK_RELAY", "gateway_endpoint_class": "LOOPBACK_GATEWAY", "provider_invocations": providerInvocations, "dummy_provider_operations": 0, "relay_exact_forwarding": relayExact}
	if err := json.NewEncoder(os.Stdout).Encode(value); err != nil {
		panic(err)
	}
}
