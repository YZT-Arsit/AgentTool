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
	"sort"
	"strconv"
	"sync"
	"time"
)

const (
	OHTTPRequestContentType  = "message/ohttp-req"
	OHTTPResponseContentType = "message/ohttp-res"
)

type RelayPublicEvent struct {
	ProfileID                string `json:"profile_id"`
	Session                  uint32 `json:"session"`
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
	ClientHTTPVersion        string `json:"client_http_version,omitempty"`
	GatewayHTTPVersion       string `json:"gateway_http_version,omitempty"`
}

type FreshRequestRelay struct {
	Profile      ScheduleProfile
	GatewayURL   string
	Client       *http.Client
	RequireHTTP2 bool

	mu                  sync.Mutex
	events              []RelayPublicEvent
	preconnectComplete  bool
	preconnectClientH2  bool
	preconnectGatewayH2 bool
}

func NewFreshRequestRelay(profile ScheduleProfile, gatewayURL string) (*FreshRequestRelay, error) {
	if err := profile.Validate(); err != nil {
		return nil, err
	}
	parsed, err := url.Parse(gatewayURL)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") {
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

// NewFreshRequestRelayWithClient is used by the canonical HTTP/2 runner.  The
// supplied client owns the one pre-established Relay->Gateway HTTP/2
// connection; the Relay never creates a per-slot transport.
func NewFreshRequestRelayWithClient(profile ScheduleProfile, gatewayURL string, client *http.Client, requireHTTP2 bool) (*FreshRequestRelay, error) {
	relay, err := NewFreshRequestRelay(profile, gatewayURL)
	if err != nil {
		return nil, err
	}
	if client == nil {
		return nil, errors.New("nil canonical Relay Gateway client")
	}
	relay.Client = client
	relay.RequireHTTP2 = requireHTTP2
	return relay, nil
}

func (r *FreshRequestRelay) servePreconnect(writer http.ResponseWriter, inbound *http.Request) {
	if inbound.Method != http.MethodGet {
		http.Error(writer, "invalid public preconnect method", http.StatusMethodNotAllowed)
		return
	}
	request, err := http.NewRequestWithContext(inbound.Context(), http.MethodGet, r.GatewayURL+"/preconnect", nil)
	if err != nil {
		http.Error(writer, "Gateway preconnect construction failed", http.StatusBadGateway)
		return
	}
	response, err := r.Client.Do(request)
	if err != nil {
		http.Error(writer, "Gateway preconnect failed", http.StatusBadGateway)
		return
	}
	response.Body.Close()
	clientH2 := inbound.ProtoMajor == 2
	gatewayH2 := response.ProtoMajor == 2
	if response.StatusCode != http.StatusNoContent || (r.RequireHTTP2 && (!clientH2 || !gatewayH2)) {
		http.Error(writer, "HTTP/2 preconnect unavailable", http.StatusBadGateway)
		return
	}
	r.mu.Lock()
	r.preconnectComplete = true
	r.preconnectClientH2 = clientH2
	r.preconnectGatewayH2 = gatewayH2
	r.mu.Unlock()
	writer.WriteHeader(http.StatusNoContent)
}

func (r *FreshRequestRelay) PreconnectStatus() (complete, clientH2, gatewayH2 bool) {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.preconnectComplete, r.preconnectClientH2, r.preconnectGatewayH2
}

func (r *FreshRequestRelay) ServeHTTP(writer http.ResponseWriter, inbound *http.Request) {
	if inbound.URL.Path == "/preconnect" {
		r.servePreconnect(writer, inbound)
		return
	}
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
	var session, round uint32
	if parsed, err := strconv.ParseUint(inbound.Header.Get("X-AgentTool-Public-Session"), 10, 32); err == nil {
		session = uint32(parsed)
	}
	if parsed, err := strconv.ParseUint(inbound.Header.Get("X-AgentTool-Public-Slot"), 10, 32); err == nil {
		round = uint32(parsed)
	}
	// Backward-compatible V8/V9 development callers used one public session
	// and X-Public-Round.  Canonical V11.1 always supplies the explicit pair.
	if session == 0 && !r.RequireHTTP2 {
		session = 1
	}
	if round == 0 && !r.RequireHTTP2 {
		_, _ = fmt.Sscanf(inbound.Header.Get("X-Public-Round"), "%d", &round)
	}
	if session == 0 || round == 0 || int(round) > r.Profile.SlotsPerSession {
		http.Error(writer, "invalid public session/slot", http.StatusBadRequest)
		return
	}
	if r.RequireHTTP2 && inbound.ProtoMajor != 2 {
		http.Error(writer, "canonical Relay requires HTTP/2", http.StatusHTTPVersionNotSupported)
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
	outbound.Header.Set("X-AgentTool-Public-Session", strconv.FormatUint(uint64(session), 10))
	outbound.Header.Set("X-AgentTool-Public-Slot", strconv.FormatUint(uint64(round), 10))
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
	if r.RequireHTTP2 && response.ProtoMajor != 2 {
		http.Error(writer, "canonical Gateway response is not HTTP/2", http.StatusBadGateway)
		return
	}
	r.record(RelayPublicEvent{
		ProfileID: r.Profile.ProfileID, Session: session, Round: round, RequestLength: len(body), ResponseLength: len(responseBody),
		RelayClientConnectionID: inbound.RemoteAddr, RelayGatewayConnectionID: gatewayConnection,
		RelayEndpoint: r.Profile.RelayEndpoint, GatewayEndpoint: r.Profile.GatewayEndpoint,
		OHTTPKeyID: r.Profile.OHTTPSuite.KeyID, KEMID: r.Profile.OHTTPSuite.KEMID,
		KDFID: r.Profile.OHTTPSuite.KDFID, AEADID: r.Profile.OHTTPSuite.AEADID,
		ConfigEpoch: r.Profile.OHTTPSuite.ConfigEpoch, RequestObservedNS: observed,
		ResponseObservedNS: time.Now().UnixNano(), ClientHTTPVersion: inbound.Proto,
		GatewayHTTPVersion: response.Proto,
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
	result := append([]RelayPublicEvent(nil), r.events...)
	// Concurrent HTTP/2 responses may complete out of order.  Slot identity is
	// public and authenticated, so the structural projection is ordered by the
	// public slot while raw request/response timestamps retain completion order.
	sort.Slice(result, func(i, j int) bool {
		if result[i].Session != result[j].Session {
			return result[i].Session < result[j].Session
		}
		return result[i].Round < result[j].Round
	})
	return result
}
