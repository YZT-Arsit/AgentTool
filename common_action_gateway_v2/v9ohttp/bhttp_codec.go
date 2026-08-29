package v9ohttp

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"

	"common-action-gateway-v2/v7ohttp"
	ohttp "github.com/chris-wood/ohttp-go"
)

const privateContentType = "application/agenttool-action+json"

const (
	StatusWait byte = iota + 1
	StatusResult
	StatusError
	StatusTimeout
	StatusEffectOutcomeUnknown
	StatusProfileOverflow
)

type privateActionWire struct {
	ProtocolVersion uint16             `json:"protocol_version"`
	PublicSession   uint32             `json:"public_session,omitempty"`
	PublicSlot      uint32             `json:"public_slot,omitempty"`
	Kind            v7ohttp.ActionKind `json:"action_kind"`
	RouteHandle     []byte             `json:"route_handle,omitempty"`
	OperationID     []byte             `json:"operation_id"`
	ProtectedArgs   []byte             `json:"protected_arguments,omitempty"`
	Continuation    []byte             `json:"continuation,omitempty"`
	Authorization   []byte             `json:"authorization,omitempty"`
}

type privateResponseWire struct {
	ProtocolVersion uint16 `json:"protocol_version"`
	PublicSession   uint32 `json:"public_session,omitempty"`
	PublicSlot      uint32 `json:"public_slot,omitempty"`
	Status          byte   `json:"result_kind"`
	OperationID     string `json:"operation_id,omitempty"`
	ProtectedResult []byte `json:"protected_result,omitempty"`
}

// RFC9292Codec delegates Binary HTTP framing to the audited ohttp-go package.
// The JSON value is the private application body, not a replacement for BHTTP.
type RFC9292Codec struct{}

func strictJSON(data []byte, value any) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(value); err != nil {
		return err
	}
	if decoder.Decode(&struct{}{}) != io.EOF {
		return errors.New("trailing private application data")
	}
	return nil
}

func padKnownLength(canonical []byte, paddedBytes int) ([]byte, error) {
	if paddedBytes < len(canonical) {
		return nil, fmt.Errorf("BHTTP message needs %d bytes, public bucket is %d", len(canonical), paddedBytes)
	}
	result := make([]byte, paddedBytes)
	copy(result, canonical)
	return result, nil
}

func validateCanonicalPadding(encoded, canonical []byte) error {
	if len(encoded) < len(canonical) || !bytes.Equal(encoded[:len(canonical)], canonical) {
		return errors.New("non-canonical BHTTP encoding")
	}
	for _, value := range encoded[len(canonical):] {
		if value != 0 {
			return errors.New("non-zero BHTTP padding")
		}
	}
	return nil
}

func (codec RFC9292Codec) EncodeKnownLengthRequest(target string, action v7ohttp.PrivateActionMessage, paddedBytes int) ([]byte, error) {
	return codec.EncodeKnownLengthRequestBound(target, action, paddedBytes, v7ohttp.SlotID{})
}

// EncodeKnownLengthRequestBound authenticates the public session/slot inside
// the OHTTP-protected BHTTP application message.  The binding is public, not
// secret; its purpose is to prevent outer-header substitution.
func (RFC9292Codec) EncodeKnownLengthRequestBound(target string, action v7ohttp.PrivateActionMessage, paddedBytes int, slot v7ohttp.SlotID) ([]byte, error) {
	if target != v7ohttp.InnerSemanticTarget {
		return nil, errors.New("unexpected private semantic target")
	}
	if err := action.Validate(); err != nil {
		return nil, err
	}
	body, err := json.Marshal(privateActionWire{
		ProtocolVersion: action.ProtocolVersion, PublicSession: slot.Session, PublicSlot: slot.Slot, Kind: action.Kind,
		RouteHandle: action.RouteHandle, OperationID: action.OperationID,
		ProtectedArgs: action.ProtectedArgs, Continuation: action.Continuation,
		Authorization: action.Authorization,
	})
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequest(http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", privateContentType)
	canonical, err := (*ohttp.BinaryRequest)(request).Marshal()
	if err != nil {
		return nil, err
	}
	return padKnownLength(canonical, paddedBytes)
}

func (codec RFC9292Codec) DecodeKnownLengthRequest(encoded []byte) (string, v7ohttp.PrivateActionMessage, error) {
	target, action, _, err := codec.DecodeKnownLengthRequestBound(encoded)
	return target, action, err
}

func (RFC9292Codec) DecodeKnownLengthRequestBound(encoded []byte) (string, v7ohttp.PrivateActionMessage, v7ohttp.SlotID, error) {
	if len(encoded) == 0 || encoded[0] != 0 {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, errors.New("not an RFC9292 known-length request")
	}
	request, err := ohttp.UnmarshalBinaryRequest(encoded)
	if err != nil {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, err
	}
	if request.Method != http.MethodPost || request.URL.String() != v7ohttp.InnerSemanticTarget ||
		request.Header.Get("Content-Type") != privateContentType {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, errors.New("invalid private BHTTP request metadata")
	}
	body, err := io.ReadAll(request.Body)
	if err != nil {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, err
	}
	request.Body = io.NopCloser(bytes.NewReader(body))
	canonical, err := (*ohttp.BinaryRequest)(request).Marshal()
	if err != nil {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, err
	}
	if err := validateCanonicalPadding(encoded, canonical); err != nil {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, err
	}
	var wire privateActionWire
	if err := strictJSON(body, &wire); err != nil {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, err
	}
	action := v7ohttp.PrivateActionMessage{
		ProtocolVersion: wire.ProtocolVersion, Kind: wire.Kind,
		RouteHandle: wire.RouteHandle, OperationID: wire.OperationID,
		ProtectedArgs: wire.ProtectedArgs, Continuation: wire.Continuation,
		Authorization: wire.Authorization,
	}
	if err := action.Validate(); err != nil {
		return "", v7ohttp.PrivateActionMessage{}, v7ohttp.SlotID{}, err
	}
	return request.URL.String(), action, v7ohttp.SlotID{Session: wire.PublicSession, Slot: wire.PublicSlot}, nil
}

func validResponseStatus(status byte) bool {
	return status >= StatusWait && status <= StatusProfileOverflow
}

func headerValueCaseInsensitive(header http.Header, name string) string {
	for key, values := range header {
		if strings.EqualFold(key, name) && len(values) > 0 {
			return values[0]
		}
	}
	return ""
}

func (codec RFC9292Codec) EncodeKnownLengthResponse(result v7ohttp.PrivateResponse, paddedBytes int) ([]byte, error) {
	return codec.EncodeKnownLengthResponseBound(result, paddedBytes, v7ohttp.SlotID{})
}

func (RFC9292Codec) EncodeKnownLengthResponseBound(result v7ohttp.PrivateResponse, paddedBytes int, slot v7ohttp.SlotID) ([]byte, error) {
	if !validResponseStatus(result.Status) {
		return nil, errors.New("invalid private response kind")
	}
	body, err := json.Marshal(privateResponseWire{
		ProtocolVersion: 1, PublicSession: slot.Session, PublicSlot: slot.Slot, Status: result.Status,
		OperationID: result.OperationID, ProtectedResult: result.Payload,
	})
	if err != nil {
		return nil, err
	}
	response := &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{privateContentType}},
		Body:       io.NopCloser(bytes.NewReader(body)),
	}
	canonical, err := (*ohttp.BinaryResponse)(response).Marshal()
	if err != nil {
		return nil, err
	}
	return padKnownLength(canonical, paddedBytes)
}

func (codec RFC9292Codec) DecodeKnownLengthResponse(encoded []byte) (v7ohttp.PrivateResponse, error) {
	result, _, err := codec.DecodeKnownLengthResponseBound(encoded)
	return result, err
}

func (RFC9292Codec) DecodeKnownLengthResponseBound(encoded []byte) (v7ohttp.PrivateResponse, v7ohttp.SlotID, error) {
	if len(encoded) == 0 || encoded[0] != 1 {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, errors.New("not an RFC9292 known-length response")
	}
	response, err := ohttp.UnmarshalBinaryResponse(encoded)
	if err != nil {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, err
	}
	// This pinned ohttp-go revision preserves RFC field names in lower case when
	// decoding BHTTP. net/http.Header.Get canonicalizes its lookup key and is
	// therefore not reliable for that map representation.
	if response.StatusCode != http.StatusOK || !strings.EqualFold(headerValueCaseInsensitive(response.Header, "Content-Type"), privateContentType) {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, errors.New("invalid private BHTTP response metadata")
	}
	body, err := io.ReadAll(response.Body)
	if err != nil {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, err
	}
	response.Body = io.NopCloser(bytes.NewReader(body))
	canonical, err := (*ohttp.BinaryResponse)(response).Marshal()
	if err != nil {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, err
	}
	if err := validateCanonicalPadding(encoded, canonical); err != nil {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, err
	}
	var wire privateResponseWire
	if err := strictJSON(body, &wire); err != nil {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, err
	}
	if wire.ProtocolVersion != 1 || !validResponseStatus(wire.Status) {
		return v7ohttp.PrivateResponse{}, v7ohttp.SlotID{}, errors.New("invalid private response schema")
	}
	return v7ohttp.PrivateResponse{Status: wire.Status, OperationID: wire.OperationID, Payload: wire.ProtectedResult}, v7ohttp.SlotID{Session: wire.PublicSession, Slot: wire.PublicSlot}, nil
}
