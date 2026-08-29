package v7ohttp

import "errors"

var ErrRFC9292Unavailable = errors.New("RFC 9292 Binary HTTP codec is not implemented in the offline dependency set")

const InnerSemanticTarget = "https://action-gateway.invalid/v1/agent-slot"

type ActionKind string

const (
	ActionNoop         ActionKind = "NOOP"
	ActionRealTool     ActionKind = "REAL_TOOL"
	ActionAgentService ActionKind = "REAL_AGENT_SERVICE"
	ActionExternalHTTP ActionKind = "REAL_EXTERNAL_HTTP"
)

// PrivateActionMessage is inner plaintext only. It must never be copied to an
// OuterMetadata or RelayObservation value.
type PrivateActionMessage struct {
	ProtocolVersion uint16
	Kind            ActionKind
	RouteHandle     []byte
	OperationID     []byte
	ProtectedArgs   []byte
	Continuation    []byte
	Authorization   []byte
}

func (m PrivateActionMessage) Validate() error {
	if m.ProtocolVersion == 0 || len(m.OperationID) == 0 {
		return errors.New("private action message is incomplete")
	}
	if m.Kind == ActionNoop {
		if len(m.RouteHandle) != 0 || len(m.ProtectedArgs) != 0 {
			return errors.New("NOOP must not contain a real route or arguments")
		}
		return nil
	}
	if len(m.RouteHandle) == 0 {
		return errors.New("real action has no private route")
	}
	return nil
}

// KnownLengthBHTTPCodec is the RFC 9292 contract expected from the selected
// third-party implementation. No local custom encoder implements this type.
type KnownLengthBHTTPCodec interface {
	EncodeKnownLengthRequest(target string, action PrivateActionMessage, paddedBytes int) ([]byte, error)
	DecodeKnownLengthRequest(encoded []byte) (string, PrivateActionMessage, error)
	EncodeKnownLengthResponse(result PrivateResponse, paddedBytes int) ([]byte, error)
	DecodeKnownLengthResponse(encoded []byte) (PrivateResponse, error)
}

// UnavailableBHTTPCodec prevents a private ad-hoc format from being labeled
// RFC 9292 when no audited standards implementation is installed.
type UnavailableBHTTPCodec struct{}

func (UnavailableBHTTPCodec) EncodeKnownLengthRequest(string, PrivateActionMessage, int) ([]byte, error) {
	return nil, ErrRFC9292Unavailable
}
func (UnavailableBHTTPCodec) DecodeKnownLengthRequest([]byte) (string, PrivateActionMessage, error) {
	return "", PrivateActionMessage{}, ErrRFC9292Unavailable
}
func (UnavailableBHTTPCodec) EncodeKnownLengthResponse(PrivateResponse, int) ([]byte, error) {
	return nil, ErrRFC9292Unavailable
}
func (UnavailableBHTTPCodec) DecodeKnownLengthResponse([]byte) (PrivateResponse, error) {
	return PrivateResponse{}, ErrRFC9292Unavailable
}
