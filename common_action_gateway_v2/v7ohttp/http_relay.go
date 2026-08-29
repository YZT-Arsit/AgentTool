package v7ohttp

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

// LocalHTTPRelay is a deliberately minimal loopback research relay. It has no
// key material and treats both request and response bodies as opaque bytes.
// The configured Gateway URL is public experiment configuration.
type LocalHTTPRelay struct {
	Profile    PublicProfile
	GatewayURL string
	Client     *http.Client

	mu           sync.Mutex
	observations []RelayObservation
	publicEvents []PublicExperimentEvent
}

func NewLocalHTTPRelay(profile PublicProfile, gatewayURL string) (*LocalHTTPRelay, error) {
	if err := profile.Validate(); err != nil {
		return nil, err
	}
	if gatewayURL == "" {
		return nil, errors.New("local Gateway URL is required")
	}
	return &LocalHTTPRelay{
		Profile:    profile,
		GatewayURL: gatewayURL,
		Client:     &http.Client{Timeout: 5 * time.Second},
	}, nil
}

func (r *LocalHTTPRelay) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	requestObserved := time.Now().UnixNano()
	if request.Method != http.MethodPost || request.Header.Get("Content-Type") != RequestContentType {
		http.Error(writer, "invalid public request metadata", http.StatusBadRequest)
		return
	}
	if request.ContentLength != int64(r.Profile.RequestEncapsulatedBytes) {
		http.Error(writer, "invalid public request length", http.StatusBadRequest)
		return
	}
	body, err := io.ReadAll(io.LimitReader(request.Body, request.ContentLength+1))
	if err != nil || len(body) != r.Profile.RequestEncapsulatedBytes {
		http.Error(writer, "invalid public request body", http.StatusBadRequest)
		return
	}

	forward, err := http.NewRequestWithContext(request.Context(), http.MethodPost, r.GatewayURL, bytes.NewReader(body))
	if err != nil {
		http.Error(writer, "local Gateway request construction failed", http.StatusBadGateway)
		return
	}
	forward.Header.Set("Content-Type", RequestContentType)
	forward.ContentLength = int64(len(body))
	response, err := r.Client.Do(forward)
	if err != nil {
		http.Error(writer, "local Gateway unavailable", http.StatusBadGateway)
		return
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK || response.Header.Get("Content-Type") != ResponseContentType {
		http.Error(writer, "invalid local Gateway response metadata", http.StatusBadGateway)
		return
	}
	if response.ContentLength != int64(r.Profile.ResponseEncapsulatedBytes) {
		http.Error(writer, "invalid local Gateway response length", http.StatusBadGateway)
		return
	}
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, response.ContentLength+1))
	if err != nil || len(responseBody) != r.Profile.ResponseEncapsulatedBytes {
		http.Error(writer, "invalid local Gateway response body", http.StatusBadGateway)
		return
	}

	connectionID := request.Header.Get("X-Public-Connection-ID")
	if connectionID == "" {
		connectionID = "LOCAL_LOOPBACK_CONNECTION"
	}
	session, slot, err := parsePublicSlotHeaders(request)
	if err != nil {
		http.Error(writer, "invalid public slot headers", http.StatusBadRequest)
		return
	}
	r.record(RelayObservation{
		Direction: "EXCHANGE", RelayEndpoint: "LOCAL_RELAY",
		GatewayEndpoint: "LOCAL_GATEWAY", ConnectionID: connectionID,
		ContentType: RequestContentType, ContentLength: len(body),
		Profile: r.Profile.Name, Session: session, Slot: slot,
	})
	r.recordPublic(PublicExperimentEvent{
		ProfileID: r.Profile.Name, Session: session, Round: slot,
		OuterRequestLength: len(body), OuterResponseLength: len(responseBody),
		RelayEndpoint: "LOCAL_RELAY", GatewayEndpoint: "LOCAL_GATEWAY",
		ConnectionID: connectionID, RequestObservedNS: requestObserved,
		ResponseObservedNS: time.Now().UnixNano(),
	})

	writer.Header().Set("Content-Type", ResponseContentType)
	writer.Header().Set("Content-Length", fmt.Sprintf("%d", len(responseBody)))
	writer.WriteHeader(http.StatusOK)
	_, _ = writer.Write(responseBody)
}

func parsePublicSlotHeaders(request *http.Request) (uint32, uint32, error) {
	var session, slot uint32
	if _, err := fmt.Sscanf(request.Header.Get("X-Public-Session"), "%d", &session); err != nil {
		return 0, 0, err
	}
	if _, err := fmt.Sscanf(request.Header.Get("X-Public-Slot"), "%d", &slot); err != nil || slot == 0 {
		return 0, 0, errors.New("invalid public slot")
	}
	return session, slot, nil
}

func (r *LocalHTTPRelay) record(observation RelayObservation) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.observations = append(r.observations, observation)
}

func (r *LocalHTTPRelay) Observations() []RelayObservation {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]RelayObservation(nil), r.observations...)
}

func (r *LocalHTTPRelay) recordPublic(event PublicExperimentEvent) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.publicEvents = append(r.publicEvents, event)
}

func (r *LocalHTTPRelay) PublicEvents() []PublicExperimentEvent {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]PublicExperimentEvent(nil), r.publicEvents...)
}
