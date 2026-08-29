package v9ohttp

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v8"
)

func TestRealOHTTPBytesTraverseV8RelayExactly(t *testing.T) {
	client, gatewayBackend, suite, _ := testBackends(t)
	codec := RFC9292Codec{}
	requestPlain, err := codec.EncodeKnownLengthRequest(
		v7ohttp.InnerSemanticTarget, action(v7ohttp.ActionRealTool), 1024,
	)
	if err != nil {
		t.Fatal(err)
	}
	probeWire, _, err := client.EncapsulateRequest(v7ohttp.SlotID{Session: 9, Slot: 99}, requestPlain)
	if err != nil {
		t.Fatal(err)
	}

	var submittedBodies [][]byte
	var gatewayBodies [][]byte
	var gatewayHeaders []http.Header
	var responseBodies [][]byte
	gatewayServer := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		body, readErr := io.ReadAll(request.Body)
		if readErr != nil {
			http.Error(writer, "read failed", http.StatusBadRequest)
			return
		}
		slot := v7ohttp.SlotID{Session: 11, Slot: uint32(len(gatewayBodies) + 1)}
		opened, serverContext, openErr := gatewayBackend.DecapsulateRequest(slot, body)
		if openErr != nil {
			http.Error(writer, "decapsulation failed", http.StatusBadRequest)
			return
		}
		_, decoded, decodeErr := codec.DecodeKnownLengthRequest(opened)
		if decodeErr != nil || decoded.Kind != v7ohttp.ActionRealTool {
			http.Error(writer, "private request invalid", http.StatusBadRequest)
			return
		}
		plainResponse, encodeErr := codec.EncodeKnownLengthResponse(v7ohttp.PrivateResponse{
			Status: StatusResult, OperationID: "op-1", Payload: []byte("protected-result"),
		}, 768)
		if encodeErr != nil {
			http.Error(writer, "response encoding failed", http.StatusInternalServerError)
			return
		}
		responseWire, sealErr := gatewayBackend.EncapsulateResponse(serverContext, plainResponse)
		if sealErr != nil {
			http.Error(writer, "response encapsulation failed", http.StatusInternalServerError)
			return
		}
		gatewayBodies = append(gatewayBodies, append([]byte(nil), body...))
		gatewayHeaders = append(gatewayHeaders, request.Header.Clone())
		responseBodies = append(responseBodies, append([]byte(nil), responseWire...))
		writer.Header().Set("Content-Type", v8.OHTTPResponseContentType)
		writer.Header().Set("Content-Length", fmt.Sprintf("%d", len(responseWire)))
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write(responseWire)
	}))
	defer gatewayServer.Close()

	profile := v8.ScheduleProfile{
		ProfileID: "V9-REAL-OHTTP-RELAY", Sessions: 1, SlotsPerSession: 2,
		RequestFinalBytes: len(probeWire), ResponseFinalBytes: 800,
		RequestIntervalNS: 1_000_000, ResponseSlotIntervalNS: 1_000_000,
		PublicLifetimeNS: 2_000_000, MaximumAdmittedOperations: 2,
		RelayEndpoint: "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY", ConnectionPolicy: "KEEP_ALIVE",
		OHTTPSuite: v8.OHTTPPublicSuite{KeyID: suite.KeyID, KEMID: suite.KEMID,
			KDFID: suite.KDFID, AEADID: suite.AEADID, ConfigEpoch: suite.ConfigurationEpoch},
	}
	relay, err := v8.NewFreshRequestRelay(profile, gatewayServer.URL)
	if err != nil {
		t.Fatal(err)
	}
	relayServer := httptest.NewServer(relay)
	defer relayServer.Close()

	for round := uint32(1); round <= 2; round++ {
		slot := v7ohttp.SlotID{Session: 11, Slot: round}
		wire, responseContext, encapsulateErr := client.EncapsulateRequest(slot, requestPlain)
		if encapsulateErr != nil {
			t.Fatal(encapsulateErr)
		}
		submittedBodies = append(submittedBodies, append([]byte(nil), wire...))
		request, _ := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(wire))
		request.Header.Set("Content-Type", v8.OHTTPRequestContentType)
		request.Header.Set("X-Public-Round", fmt.Sprintf("%d", round))
		request.Header.Set("Cookie", "private-cookie")
		request.Header.Set("Authorization", "private-authorization")
		request.Header.Set("X-Agent-ID", "private-agent")
		request.Header.Set("User-Agent", "private-user-agent")
		request.ContentLength = int64(len(wire))
		response, requestErr := relayServer.Client().Do(request)
		if requestErr != nil {
			t.Fatal(requestErr)
		}
		responseWire, readErr := io.ReadAll(response.Body)
		response.Body.Close()
		if readErr != nil || response.StatusCode != http.StatusOK {
			t.Fatalf("relay response: status=%d err=%v", response.StatusCode, readErr)
		}
		if !bytes.Equal(responseWire, responseBodies[round-1]) {
			t.Fatal("relay changed the Gateway OHTTP response body")
		}
		opened, openErr := client.DecapsulateResponse(responseContext, responseWire)
		if openErr != nil {
			t.Fatal(openErr)
		}
		decoded, decodeErr := codec.DecodeKnownLengthResponse(opened)
		if decodeErr != nil || decoded.OperationID != "op-1" || !bytes.Equal(decoded.Payload, []byte("protected-result")) {
			t.Fatalf("private response changed: response=%+v err=%v", decoded, decodeErr)
		}
	}

	events := relay.Events()
	if len(gatewayBodies) != 2 || len(responseBodies) != 2 || len(events) != 2 {
		t.Fatal("real OHTTP relay did not record two complete rounds")
	}
	for index, event := range events {
		if !bytes.Equal(gatewayBodies[index], submittedBodies[index]) ||
			event.RequestLength != profile.RequestFinalBytes || event.ResponseLength != profile.ResponseFinalBytes {
			t.Fatal("relay changed OHTTP bytes or public lengths")
		}
		for _, forbidden := range []string{"Cookie", "Authorization", "X-Agent-ID"} {
			if gatewayHeaders[index].Get(forbidden) != "" {
				t.Fatalf("relay forwarded forbidden header %s", forbidden)
			}
		}
		if gatewayHeaders[index].Get("User-Agent") == "private-user-agent" {
			t.Fatal("relay forwarded client User-Agent")
		}
	}
	if events[0].RelayGatewayConnectionID != events[1].RelayGatewayConnectionID {
		t.Fatal("relay did not reuse its loopback Gateway connection")
	}
}
