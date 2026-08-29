// Package v7ohttp defines the canonical V7-OHTTP transport boundary.
//
// It intentionally contains no home-grown HPKE or Binary HTTP implementation.
// A backend may report RFC9458Wire only when it is backed by an audited RFC
// 9458 implementation with RFC 9292 known-length message support.
package v7ohttp

import (
	"errors"
	"fmt"
)

var ErrRFC9458Unavailable = errors.New("RFC 9458 OHTTP wire is not implemented in the offline dependency set")

const (
	RequestContentType  = "message/ohttp-req"
	ResponseContentType = "message/ohttp-res"
)

type BackendStatus string

const (
	BackendPass                  BackendStatus = "PASS"
	BackendPartial               BackendStatus = "PARTIAL"
	BackendNotImplementedOffline BackendStatus = "NOT_IMPLEMENTED_OFFLINE"
	BackendFail                  BackendStatus = "FAIL"
)

type GatewayKeyConfiguration struct {
	KeyID               uint8
	KEMID               uint16
	KDFID               uint16
	AEADID              uint16
	PublicKey           []byte
	RotationEpoch       uint64
	AuthenticatedSource string
}

func (c GatewayKeyConfiguration) Validate() error {
	if len(c.PublicKey) == 0 || c.AuthenticatedSource == "" {
		return errors.New("incomplete authenticated Gateway key configuration")
	}
	return nil
}

// ClientContext is opaque backend-owned state for exactly one unary OHTTP
// request/response exchange. Contexts must never be reused across slots.
type ClientContext interface {
	Slot() SlotID
}

type ServerContext interface {
	Slot() SlotID
}

type ClientBackend interface {
	Name() string
	Status() BackendStatus
	RFC9458Wire() bool
	EncapsulateRequest(slot SlotID, bhttpRequest []byte) ([]byte, ClientContext, error)
	DecapsulateResponse(context ClientContext, encapsulatedResponse []byte) ([]byte, error)
}

type GatewayBackend interface {
	Name() string
	Status() BackendStatus
	RFC9458Wire() bool
	DecapsulateRequest(slot SlotID, encapsulatedRequest []byte) ([]byte, ServerContext, error)
	EncapsulateResponse(context ServerContext, bhttpResponse []byte) ([]byte, error)
}

type UnavailableBackend struct{}

func (UnavailableBackend) Name() string          { return "RFC9458_OHTTP_NOT_IMPLEMENTED_OFFLINE" }
func (UnavailableBackend) Status() BackendStatus { return BackendNotImplementedOffline }
func (UnavailableBackend) RFC9458Wire() bool     { return false }
func (UnavailableBackend) EncapsulateRequest(SlotID, []byte) ([]byte, ClientContext, error) {
	return nil, nil, ErrRFC9458Unavailable
}
func (UnavailableBackend) DecapsulateResponse(ClientContext, []byte) ([]byte, error) {
	return nil, ErrRFC9458Unavailable
}
func (UnavailableBackend) DecapsulateRequest(SlotID, []byte) ([]byte, ServerContext, error) {
	return nil, nil, ErrRFC9458Unavailable
}
func (UnavailableBackend) EncapsulateResponse(ServerContext, []byte) ([]byte, error) {
	return nil, ErrRFC9458Unavailable
}

// RequireCanonical prevents an unavailable or legacy backend from entering the
// canonical experiment path.
func RequireCanonical(name string, status BackendStatus, rfc9458 bool) error {
	if !rfc9458 || status != BackendPass {
		return fmt.Errorf("canonical V7-OHTTP requires PASS RFC9458 backend: backend=%s status=%s", name, status)
	}
	return nil
}
