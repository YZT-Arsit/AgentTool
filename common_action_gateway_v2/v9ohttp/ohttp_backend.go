package v9ohttp

import (
	"encoding/binary"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"

	"common-action-gateway-v2/v7ohttp"
	ohttp "github.com/chris-wood/ohttp-go"
)

type PublicSuite struct {
	KeyID               uint8
	KEMID               uint16
	KDFID               uint16
	AEADID              uint16
	ConfigurationEpoch  uint64
	AuthenticatedSource string
}

func (s PublicSuite) Validate(config ohttp.PublicConfig) error {
	if s.AuthenticatedSource == "" || s.KEMID == 0 || s.KDFID == 0 || s.AEADID == 0 {
		return errors.New("invalid public OHTTP suite")
	}
	if config.ID != s.KeyID || uint16(config.KEMID) != s.KEMID || len(config.Suites) == 0 ||
		uint16(config.Suites[0].KDFID) != s.KDFID || uint16(config.Suites[0].AEADID) != s.AEADID {
		return errors.New("selected suite does not match Gateway key configuration")
	}
	return nil
}

type clientContext struct {
	slot  v7ohttp.SlotID
	inner ohttp.EncapsulatedRequestContext
	used  atomic.Bool
}

func (c *clientContext) Slot() v7ohttp.SlotID { return c.slot }

type serverContext struct {
	slot  v7ohttp.SlotID
	inner ohttp.DecapsulateRequestContext
	used  atomic.Bool
}

func (c *serverContext) Slot() v7ohttp.SlotID { return c.slot }

type RFC9458Client struct {
	client ohttp.Client
	suite  PublicSuite
}

type RFC9458Gateway struct {
	gateway ohttp.Gateway
	suite   PublicSuite
	// The pinned ohttp-go Gateway mutates receiver-owned HPKE state while
	// decapsulating. HTTP/2 handlers may arrive concurrently, so serialize only
	// this private pre-commit operation. Per-request response contexts remain
	// independent and response encoding stays off the public release path.
	decapsulationMu sync.Mutex
}

func NewRFC9458Client(config ohttp.PublicConfig, suite PublicSuite) (*RFC9458Client, error) {
	if err := suite.Validate(config); err != nil {
		return nil, err
	}
	return &RFC9458Client{client: ohttp.NewDefaultClient(config), suite: suite}, nil
}

func NewRFC9458Gateway(config ohttp.PrivateConfig, suite PublicSuite) (*RFC9458Gateway, error) {
	if err := suite.Validate(config.Config()); err != nil {
		return nil, err
	}
	return &RFC9458Gateway{gateway: ohttp.NewDefaultGateway([]ohttp.PrivateConfig{config}), suite: suite}, nil
}

func (*RFC9458Client) Name() string                   { return "OHTTP_GO_RFC9458_V9" }
func (*RFC9458Client) Status() v7ohttp.BackendStatus  { return v7ohttp.BackendPass }
func (*RFC9458Client) RFC9458Wire() bool              { return true }
func (*RFC9458Gateway) Name() string                  { return "OHTTP_GO_RFC9458_V9" }
func (*RFC9458Gateway) Status() v7ohttp.BackendStatus { return v7ohttp.BackendPass }
func (*RFC9458Gateway) RFC9458Wire() bool             { return true }

func (c *RFC9458Client) EncapsulateRequest(slot v7ohttp.SlotID, bhttpRequest []byte) ([]byte, v7ohttp.ClientContext, error) {
	request, context, err := c.client.EncapsulateRequest(bhttpRequest)
	if err != nil {
		return nil, nil, err
	}
	return request.Marshal(), &clientContext{slot: slot, inner: context}, nil
}

func responseMinimum(aeadID uint16) (int, error) {
	keySize := 0
	switch aeadID {
	case 0x0001: // AES-128-GCM
		keySize = 16
	case 0x0002, 0x0003: // AES-256-GCM, ChaCha20Poly1305
		keySize = 32
	default:
		return 0, errors.New("unsupported response AEAD size")
	}
	nonceSize := 12
	if keySize > nonceSize {
		nonceSize = keySize
	}
	return nonceSize + 16, nil
}

func (c *RFC9458Client) DecapsulateResponse(rawContext v7ohttp.ClientContext, encapsulatedResponse []byte) (plaintext []byte, err error) {
	context, ok := rawContext.(*clientContext)
	if !ok || context == nil {
		return nil, errors.New("foreign OHTTP client context")
	}
	if !context.used.CompareAndSwap(false, true) {
		return nil, errors.New("OHTTP client context reuse")
	}
	minimum, err := responseMinimum(c.suite.AEADID)
	if err != nil || len(encapsulatedResponse) < minimum {
		return nil, errors.New("truncated encapsulated OHTTP response")
	}
	defer func() {
		if recovered := recover(); recovered != nil {
			plaintext = nil
			err = fmt.Errorf("malformed encapsulated OHTTP response")
		}
	}()
	response, err := ohttp.UnmarshalEncapsulatedResponse(encapsulatedResponse)
	if err != nil {
		return nil, err
	}
	return context.inner.DecapsulateResponse(response)
}

func validateWireSuite(message []byte, suite PublicSuite) error {
	if len(message) < 7 {
		return errors.New("truncated encapsulated OHTTP request")
	}
	if message[0] != suite.KeyID || binary.BigEndian.Uint16(message[1:3]) != suite.KEMID ||
		binary.BigEndian.Uint16(message[3:5]) != suite.KDFID ||
		binary.BigEndian.Uint16(message[5:7]) != suite.AEADID {
		return errors.New("encapsulated request uses unconfigured public suite")
	}
	return nil
}

func (g *RFC9458Gateway) DecapsulateRequest(slot v7ohttp.SlotID, encapsulatedRequest []byte) ([]byte, v7ohttp.ServerContext, error) {
	if err := validateWireSuite(encapsulatedRequest, g.suite); err != nil {
		return nil, nil, err
	}
	request, err := ohttp.UnmarshalEncapsulatedRequest(encapsulatedRequest)
	if err != nil {
		return nil, nil, err
	}
	g.decapsulationMu.Lock()
	plaintext, context, err := g.gateway.DecapsulateRequest(request)
	g.decapsulationMu.Unlock()
	if err != nil {
		return nil, nil, err
	}
	return plaintext, &serverContext{slot: slot, inner: context}, nil
}

func (g *RFC9458Gateway) EncapsulateResponse(rawContext v7ohttp.ServerContext, bhttpResponse []byte) ([]byte, error) {
	context, ok := rawContext.(*serverContext)
	if !ok || context == nil {
		return nil, errors.New("foreign OHTTP server context")
	}
	if !context.used.CompareAndSwap(false, true) {
		return nil, errors.New("OHTTP server context reuse")
	}
	response, err := context.inner.EncapsulateResponse(bhttpResponse)
	if err != nil {
		return nil, err
	}
	return response.Marshal(), nil
}
