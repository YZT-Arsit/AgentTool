package v8

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	gatewayv2 "common-action-gateway-v2"
	v7 "common-action-gateway-v2/v7"
)

func scheduleProfile() ScheduleProfile {
	return ScheduleProfile{ProfileID: "V8-LOCAL", Sessions: 1, SlotsPerSession: 256,
		RequestFinalBytes: 1024, ResponseFinalBytes: 1024,
		RequestIntervalNS: 50_000_000, ResponseSlotIntervalNS: 50_000_000,
		ResponseLagNS: 25_000_000, PublicLifetimeNS: 12_800_000_000,
		MaximumAdmittedOperations: 100, TerminalSlots: 1, ProviderCompletionBoundNS: 500_000_000,
		RelayEndpoint: "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY", ConnectionPolicy: "KEEP_ALIVE",
		OHTTPSuite: OHTTPPublicSuite{KeyID: 1, KEMID: 32, KDFID: 1, AEADID: 1, ConfigEpoch: 1}}
}

func TestAdmissionIsMechanicallyBoundToActualSchedule(t *testing.T) {
	p := scheduleProfile()
	a := v7.AdmissionProfile{Sessions: 1, SlotsPerSession: 256, AdmissionSlots: 100,
		MaxRealOperations: 100, SlotIntervalNS: 50_000_000,
		ProviderCompletionBoundNS: 500_000_000, TerminalSlots: 1}
	if err := BindAdmission(p, a); err != nil {
		t.Fatal(err)
	}
	a.SlotIntervalNS++
	if BindAdmission(p, a) == nil {
		t.Fatal("admission passed with different scheduler interval")
	}
}

func TestMemoryDeliveryCutoffAndDeadlinePathPerformNoDurabilityIO(t *testing.T) {
	queue, _ := NewMemoryDeliveryQueue(2)
	result := gatewayv2.ResultRecord{Session: 0, Status: gatewayv2.StatusOK,
		OperationID: gatewayv2.OperationID("op")}
	if err := queue.PublishDurable(result); err != nil {
		t.Fatal(err)
	}
	selected := queue.SnapshotEligible(0)
	if selected == nil {
		t.Fatal("durable result was not snapshotted in memory")
	}
	ack := make(chan string, 1)
	frame := bytes.Repeat([]byte{0x55}, 1024)
	prepared := PreparedSlot{Frame: frame, OperationID: "op", Ack: ack}
	var wire bytes.Buffer
	if err := prepared.Send(&wire); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(wire.Bytes(), frame) || <-ack != "op" {
		t.Fatal("minimal send/ack path changed prepared response")
	}
}

func TestFreshRequestRelayDropsAllNonAllowlistedInboundMetadata(t *testing.T) {
	profile := scheduleProfile()
	responseBody := bytes.Repeat([]byte{0x44}, profile.ResponseFinalBytes)
	seen := make(chan http.Header, 1)
	gateway := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		_, _ = io.ReadAll(request.Body)
		seen <- request.Header.Clone()
		writer.Header().Set("Content-Type", OHTTPResponseContentType)
		writer.Header().Set("Content-Length", fmt.Sprintf("%d", len(responseBody)))
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write(responseBody)
	}))
	defer gateway.Close()
	relay, err := NewFreshRequestRelay(profile, gateway.URL)
	if err != nil {
		t.Fatal(err)
	}
	relayServer := httptest.NewServer(relay)
	defer relayServer.Close()
	body := bytes.Repeat([]byte{0x33}, profile.RequestFinalBytes)
	request, _ := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(body))
	request.Header.Set("Content-Type", OHTTPRequestContentType)
	request.Header.Set("X-Public-Round", "1")
	request.ContentLength = int64(len(body))
	for key, value := range map[string]string{
		"Forwarded": "for=private", "X-Forwarded-For": "private", "Via": "private",
		"Cookie": "private", "Authorization": "private", "User-Agent": "private-client-agent",
		"X-Agent-ID": "private-agent", "X-Tool": "private-tool",
	} {
		request.Header.Set(key, value)
	}
	response, err := relayServer.Client().Do(request)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	headers := <-seen
	for _, key := range []string{"Forwarded", "X-Forwarded-For", "Via", "Cookie", "Authorization", "X-Agent-ID", "X-Tool"} {
		if headers.Get(key) != "" {
			t.Fatalf("inbound private header reached Gateway: %s", key)
		}
	}
	if headers.Get("User-Agent") == "private-client-agent" {
		t.Fatal("client-specific User-Agent reached Gateway")
	}
	events := relay.Events()
	if len(events) != 1 || events[0].RelayClientConnectionID == "" || events[0].RelayGatewayConnectionID == "" {
		t.Fatal("separate Relay connection identities were not recorded")
	}
	encoded, _ := json.Marshal(events)
	for _, forbidden := range [][]byte{[]byte("operation_id"), []byte("agent"), []byte("tool"), []byte("body_digest")} {
		if bytes.Contains(bytes.ToLower(encoded), forbidden) {
			t.Fatalf("private semantic field appeared in Relay log: %s", forbidden)
		}
	}
}

func TestFreshRequestRelayRefusesNonLoopbackGateway(t *testing.T) {
	if _, err := NewFreshRequestRelay(scheduleProfile(), "http://example.invalid/ohttp"); err == nil {
		t.Fatal("research Relay accepted non-loopback Gateway")
	}
}
