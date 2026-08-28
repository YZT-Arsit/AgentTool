package gatewayv2

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"time"
)

type ProviderConfig struct {
	Endpoints        map[string]string `json:"endpoints"`
	Effectful        map[string]bool   `json:"effectful,omitempty"`
	TimeoutMS        int               `json:"timeout_ms"`
	AllowGenericHTTP bool              `json:"allow_generic_http"`
}

func LoadProviderConfig(path string) (ProviderConfig, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ProviderConfig{}, err
	}
	var config ProviderConfig
	if err := json.Unmarshal(raw, &config); err != nil {
		return ProviderConfig{}, err
	}
	if config.TimeoutMS <= 0 {
		config.TimeoutMS = 5000
	}
	return config, nil
}

type ProviderAdapter interface {
	Execute(context.Context, PrivateOperation) ResultRecord
	IsEffectful(byte) bool
}

type HTTPProviderAdapter struct {
	client       *http.Client
	endpoints    map[byte]string
	effectful    map[string]bool
	allowGeneric bool
}

type LocalProviderAdapter struct{ delegate *HTTPProviderAdapter }
type GenericHTTPProviderAdapter struct{ delegate *HTTPProviderAdapter }

func NewLocalProviderAdapter(config ProviderConfig) (*LocalProviderAdapter, error) {
	config.AllowGenericHTTP = false
	delegate, err := NewHTTPProviderAdapter(config)
	if err != nil {
		return nil, err
	}
	return &LocalProviderAdapter{delegate: delegate}, nil
}

func (a *LocalProviderAdapter) Execute(ctx context.Context, op PrivateOperation) ResultRecord {
	return a.delegate.Execute(ctx, op)
}
func (a *LocalProviderAdapter) IsEffectful(provider byte) bool {
	return a.delegate.IsEffectful(provider)
}

func NewGenericHTTPProviderAdapter(config ProviderConfig) (*GenericHTTPProviderAdapter, error) {
	if !config.AllowGenericHTTP {
		return nil, errors.New("generic HTTP provider is disabled")
	}
	delegate, err := NewHTTPProviderAdapter(config)
	if err != nil {
		return nil, err
	}
	return &GenericHTTPProviderAdapter{delegate: delegate}, nil
}

func (a *GenericHTTPProviderAdapter) Execute(ctx context.Context, op PrivateOperation) ResultRecord {
	return a.delegate.Execute(ctx, op)
}
func (a *GenericHTTPProviderAdapter) IsEffectful(provider byte) bool {
	return a.delegate.IsEffectful(provider)
}

func providerName(code byte) string {
	switch code {
	case ProviderFast:
		return "FAST"
	case ProviderMedium:
		return "MEDIUM"
	case ProviderSlow:
		return "SLOW"
	case ProviderVerySlow:
		return "VERY_SLOW"
	case ProviderJittered:
		return "JITTERED"
	case ProviderLocalModel:
		return "LOCAL_MODEL"
	case ProviderReadOnly:
		return "READ_ONLY_TOOL"
	case ProviderEffectful:
		return "EFFECTFUL_TOOL"
	default:
		return "NONE"
	}
}

func NewHTTPProviderAdapter(config ProviderConfig) (*HTTPProviderAdapter, error) {
	endpoints := make(map[byte]string)
	for code := ProviderFast; code <= ProviderEffectful; code++ {
		name := providerName(code)
		endpoint, ok := config.Endpoints[name]
		if !ok {
			continue
		}
		parsed, err := url.Parse(endpoint)
		if err != nil {
			return nil, err
		}
		if parsed.Scheme != "http" && parsed.Scheme != "https" {
			return nil, fmt.Errorf("unsupported provider scheme %q", parsed.Scheme)
		}
		host := parsed.Hostname()
		ip := net.ParseIP(host)
		isLocal := host == "localhost" || (ip != nil && ip.IsLoopback())
		if !isLocal && !config.AllowGenericHTTP {
			return nil, fmt.Errorf("non-loopback provider %q disabled", endpoint)
		}
		endpoints[code] = endpoint
	}
	transport := &http.Transport{
		MaxIdleConns:        128,
		MaxIdleConnsPerHost: 64,
		IdleConnTimeout:     30 * time.Second,
		DisableCompression:  true,
	}
	return &HTTPProviderAdapter{
		client:    &http.Client{Transport: transport, Timeout: time.Duration(config.TimeoutMS) * time.Millisecond},
		endpoints: endpoints, effectful: config.Effectful, allowGeneric: config.AllowGenericHTTP,
	}, nil
}

func (a *HTTPProviderAdapter) IsEffectful(provider byte) bool {
	return a.effectful[providerName(provider)]
}

type providerRequest struct {
	OperationID string `json:"operation_id"`
	Payload     []byte `json:"payload"`
}

type providerResponse struct {
	Status  string `json:"status"`
	Payload []byte `json:"payload"`
}

func baseResult(op PrivateOperation) ResultRecord {
	return ResultRecord{Session: op.Session, RequestSlot: op.Slot, OperationID: op.OperationID}
}

func (a *HTTPProviderAdapter) Execute(ctx context.Context, op PrivateOperation) ResultRecord {
	result := baseResult(op)
	endpoint, ok := a.endpoints[op.Provider]
	if !ok {
		result.Status = StatusError
		return result
	}
	body, _ := json.Marshal(providerRequest{OperationID: OperationIDString(op.OperationID), Payload: op.Payload})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		result.Status = StatusError
		return result
	}
	req.Header.Set("Content-Type", "application/json")
	response, err := a.client.Do(req)
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(ctx.Err(), context.DeadlineExceeded) {
			result.Status = StatusTimeout
		} else if errors.Is(ctx.Err(), context.Canceled) {
			result.Status = StatusCancelled
		} else {
			result.Status = StatusError
		}
		return result
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(response.Body, ResultPayloadBytes+1024))
	if err != nil || response.StatusCode/100 != 2 {
		result.Status = StatusError
		return result
	}
	var decoded providerResponse
	if err := json.Unmarshal(raw, &decoded); err != nil {
		result.Status = StatusError
		return result
	}
	if len(decoded.Payload) > ResultPayloadBytes {
		decoded.Payload = decoded.Payload[:ResultPayloadBytes]
	}
	result.Status = StatusOK
	result.PayloadLen = uint16(len(decoded.Payload))
	copy(result.Payload[:], decoded.Payload)
	return result
}
