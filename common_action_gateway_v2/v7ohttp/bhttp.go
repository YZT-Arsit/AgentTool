package v7ohttp

import "errors"

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
