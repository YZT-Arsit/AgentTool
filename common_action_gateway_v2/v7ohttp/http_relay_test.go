package v7ohttp

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
)

func TestLocalHTTPRelayForwardsExactBytesAndReusesGatewayConnection(t *testing.T) {
	profile := testProfile()
	requestBodies := make([][]byte, 0, 2)
	remoteAddresses := make([]string, 0, 2)
	var mutex sync.Mutex
	responseBody := bytes.Repeat([]byte{0x5a}, profile.ResponseEncapsulatedBytes)
	gateway := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		body, err := io.ReadAll(request.Body)
		if err != nil {
			t.Error(err)
			return
		}
		mutex.Lock()
		requestBodies = append(requestBodies, body)
		remoteAddresses = append(remoteAddresses, request.RemoteAddr)
		mutex.Unlock()
		if request.Header.Get("Content-Type") != RequestContentType || request.ContentLength != int64(profile.RequestEncapsulatedBytes) {
			t.Error("Gateway received altered public metadata")
		}
		writer.Header().Set("Content-Type", ResponseContentType)
		writer.Header().Set("Content-Length", fmt.Sprintf("%d", len(responseBody)))
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write(responseBody)
	}))
	defer gateway.Close()

	relay, err := NewLocalHTTPRelay(profile, gateway.URL)
	if err != nil {
		t.Fatal(err)
	}
	relayServer := httptest.NewServer(relay)
	defer relayServer.Close()
	client := relayServer.Client()
	for slot := 1; slot <= 2; slot++ {
		requestBody := bytes.Repeat([]byte{byte(0xa0 + slot)}, profile.RequestEncapsulatedBytes)
		request, _ := http.NewRequest(http.MethodPost, relayServer.URL, bytes.NewReader(requestBody))
		request.Header.Set("Content-Type", RequestContentType)
		request.Header.Set("X-Public-Connection-ID", "public-connection-1")
		request.Header.Set("X-Public-Session", "0")
		request.Header.Set("X-Public-Slot", string(rune('0'+slot)))
		request.ContentLength = int64(len(requestBody))
		response, err := client.Do(request)
		if err != nil {
			t.Fatal(err)
		}
		got, _ := io.ReadAll(response.Body)
		response.Body.Close()
		if !bytes.Equal(got, responseBody) || response.Header.Get("Content-Type") != ResponseContentType {
			t.Fatal("Relay changed Gateway response")
		}
	}
	if len(requestBodies) != 2 || bytes.Equal(requestBodies[0], requestBodies[1]) {
		t.Fatal("test requests did not reach Gateway distinctly")
	}
	for index, got := range requestBodies {
		want := bytes.Repeat([]byte{byte(0xa1 + index)}, profile.RequestEncapsulatedBytes)
		if !bytes.Equal(got, want) {
			t.Fatal("Relay changed trusted request bytes")
		}
	}
	if len(remoteAddresses) != 2 {
		t.Fatal("missing Gateway connection observations")
	}
	firstHost, firstPort, _ := net.SplitHostPort(remoteAddresses[0])
	secondHost, secondPort, _ := net.SplitHostPort(remoteAddresses[1])
	if firstHost != secondHost || firstPort != secondPort {
		t.Fatalf("Relay did not reuse Gateway connection: %v", remoteAddresses)
	}
	observations := relay.Observations()
	if len(observations) != 2 || observations[0].ContentLength != profile.RequestEncapsulatedBytes {
		t.Fatal("public Relay observations are incomplete")
	}
	publicEvents := relay.PublicEvents()
	if len(publicEvents) != 2 || publicEvents[0].OuterResponseLength != profile.ResponseEncapsulatedBytes {
		t.Fatal("separated public experiment log is incomplete")
	}
	serialized, _ := json.Marshal(publicEvents)
	for _, forbidden := range [][]byte{[]byte("operation_id"), []byte("action_class"), []byte("local_emulator"), []byte("result_status")} {
		if bytes.Contains(serialized, forbidden) {
			t.Fatalf("private field appeared in public log: %s", forbidden)
		}
	}
}

func TestLocalHTTPRelayRejectsVariableLengthBeforeGateway(t *testing.T) {
	profile := testProfile()
	gatewayCalls := 0
	gateway := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { gatewayCalls++ }))
	defer gateway.Close()
	relay, _ := NewLocalHTTPRelay(profile, gateway.URL)
	server := httptest.NewServer(relay)
	defer server.Close()
	request, _ := http.NewRequest(http.MethodPost, server.URL, bytes.NewReader(make([]byte, 17)))
	request.Header.Set("Content-Type", RequestContentType)
	request.ContentLength = 17
	response, err := server.Client().Do(request)
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != http.StatusBadRequest || gatewayCalls != 0 {
		t.Fatal("variable-size request reached Gateway")
	}
}

func TestUnavailableBHTTPCodecFailsClosed(t *testing.T) {
	codec := UnavailableBHTTPCodec{}
	if _, err := codec.EncodeKnownLengthRequest(InnerSemanticTarget, PrivateActionMessage{}, 1024); err != ErrRFC9292Unavailable {
		t.Fatalf("unexpected BHTTP status: %v", err)
	}
}
