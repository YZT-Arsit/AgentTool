package v8

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptrace"
	"net/url"
	"sync"
	"time"
)

const (
	OHTTPRequestContentType  = "message/ohttp-req"
	OHTTPResponseContentType = "message/ohttp-res"
)

type RelayPublicEvent struct {
	ProfileID                string `json:"profile_id"`
	Round                    uint32 `json:"round"`
	RequestLength            int    `json:"request_length"`
	ResponseLength           int    `json:"response_length"`
	RelayClientConnectionID  string `json:"relay_client_connection_id"`
	RelayGatewayConnectionID string `json:"relay_gateway_connection_id"`
	RelayEndpoint            string `json:"relay_endpoint"`
	GatewayEndpoint          string `json:"gateway_endpoint"`
	OHTTPKeyID               uint8  `json:"ohttp_key_id"`
	KEMID                    uint16 `json:"kem_id"`
	KDFID                    uint16 `json:"kdf_id"`
	AEADID                   uint16 `json:"aead_id"`
	ConfigEpoch              uint64 `json:"config_epoch"`
	RequestObservedNS        int64  `json:"request_observed_ns"`
	ResponseObservedNS       int64  `json:"response_observed_ns"`
}

type FreshRequestRelay struct {
	Profile    ScheduleProfile
	GatewayURL string
	Client     *http.Client

	mu     sync.Mutex
	events []RelayPublicEvent
}

func NewFreshRequestRelay(profile ScheduleProfile, gatewayURL string) (*FreshRequestRelay, error) {
	if err := profile.Validate(); err != nil {
		return nil, err
	}
	parsed, err := url.Parse(gatewayURL)
	if err != nil || parsed.Scheme != "http" {
		return nil, errors.New("V8 research Relay requires local HTTP Gateway URL")
	}
	host := parsed.Hostname()
	ip := net.ParseIP(host)
	if host != "localhost" && (ip == nil || !ip.IsLoopback()) {
		return nil, errors.New("V8 research Relay refuses non-loopback Gateway")
	}
	transport := &http.Transport{MaxIdleConns: 2, MaxIdleConnsPerHost: 1, IdleConnTimeout: 30 * time.Second}
	return &FreshRequestRelay{Profile: profile, GatewayURL: gatewayURL,
		Client: &http.Client{Transport: transport, Timeout: 5 * time.Second}}, nil
}

func (r *FreshRequestRelay) ServeHTTP(writer http.ResponseWriter, inbound *http.Request) {
	observed := time.Now().UnixNano()
	if inbound.Method != http.MethodPost || inbound.Header.Get("Content-Type") != OHTTPRequestContentType ||
		inbound.ContentLength != int64(r.Profile.RequestFinalBytes) {
		http.Error(writer, "invalid public OHTTP request metadata", http.StatusBadRequest)
		return
	}
	body, err := io.ReadAll(io.LimitReader(inbound.Body, inbound.ContentLength+1))
	if err != nil || len(body) != r.Profile.RequestFinalBytes {
		http.Error(writer, "invalid public OHTTP request body", http.StatusBadRequest)
		return
	}
	var gatewayConnection string
	trace := &httptrace.ClientTrace{GotConn: func(info httptrace.GotConnInfo) {
		gatewayConnection = info.Conn.LocalAddr().String() + "->" + info.Conn.RemoteAddr().String()
	}}
	context := httptrace.WithClientTrace(inbound.Context(), trace)
	outbound, err := http.NewRequestWithContext(context, http.MethodPost, r.GatewayURL, bytes.NewReader(body))
	if err != nil {
		http.Error(writer, "local Gateway request construction failed", http.StatusBadGateway)
		return
	}
	// Explicit allowlist: no inbound header map is copied.
	outbound.Header.Set("Content-Type", OHTTPRequestContentType)
	outbound.Header["User-Agent"] = []string{}
	outbound.ContentLength = int64(len(body))
	response, err := r.Client.Do(outbound)
	if err != nil {
		http.Error(writer, "local Gateway unavailable", http.StatusBadGateway)
		return
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK || response.Header.Get("Content-Type") != OHTTPResponseContentType ||
		response.ContentLength != int64(r.Profile.ResponseFinalBytes) {
		http.Error(writer, "invalid local Gateway response", http.StatusBadGateway)
		return
	}
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, response.ContentLength+1))
	if err != nil || len(responseBody) != r.Profile.ResponseFinalBytes {
		http.Error(writer, "invalid local Gateway response body", http.StatusBadGateway)
		return
	}
	var round uint32
	if _, err := fmt.Sscanf(inbound.Header.Get("X-Public-Round"), "%d", &round); err != nil || round == 0 {
		http.Error(writer, "invalid public round", http.StatusBadRequest)
		return
	}
	r.record(RelayPublicEvent{
		ProfileID: r.Profile.ProfileID, Round: round, RequestLength: len(body), ResponseLength: len(responseBody),
		RelayClientConnectionID: inbound.RemoteAddr, RelayGatewayConnectionID: gatewayConnection,
		RelayEndpoint: r.Profile.RelayEndpoint, GatewayEndpoint: r.Profile.GatewayEndpoint,
		OHTTPKeyID: r.Profile.OHTTPSuite.KeyID, KEMID: r.Profile.OHTTPSuite.KEMID,
		KDFID: r.Profile.OHTTPSuite.KDFID, AEADID: r.Profile.OHTTPSuite.AEADID,
		ConfigEpoch: r.Profile.OHTTPSuite.ConfigEpoch, RequestObservedNS: observed,
		ResponseObservedNS: time.Now().UnixNano(),
	})
	writer.Header().Set("Content-Type", OHTTPResponseContentType)
	writer.Header().Set("Content-Length", fmt.Sprintf("%d", len(responseBody)))
	writer.WriteHeader(http.StatusOK)
	_, _ = writer.Write(responseBody)
}

func (r *FreshRequestRelay) record(event RelayPublicEvent) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.events = append(r.events, event)
}

func (r *FreshRequestRelay) Events() []RelayPublicEvent {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]RelayPublicEvent(nil), r.events...)
}
