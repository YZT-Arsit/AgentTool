package v7ohttp

import (
	"bytes"
	"errors"
	"io"
)

// RelayObservation contains only public transport metadata. In particular it
// has no body digest because a digest could become a stable linkability token.
type RelayObservation struct {
	Direction       string
	RelayEndpoint   string
	GatewayEndpoint string
	ConnectionID    string
	ContentType     string
	ContentLength   int
	Profile         string
	Session         uint32
	Slot            uint32
}

type OpaqueRelay struct {
	Profile      PublicProfile
	Observations []RelayObservation
}

func (r *OpaqueRelay) ForwardRequest(metadata OuterMetadata, body []byte, destination io.Writer) error {
	if err := ValidateRequestMetadata(r.Profile, metadata); err != nil {
		return err
	}
	if len(body) != metadata.ContentLength {
		return errors.New("request body length differs from fixed Content-Length")
	}
	return r.forward("REQUEST", metadata, body, destination)
}

func (r *OpaqueRelay) ForwardResponse(metadata OuterMetadata, body []byte, destination io.Writer) error {
	if err := ValidateResponseMetadata(r.Profile, metadata); err != nil {
		return err
	}
	if len(body) != metadata.ContentLength {
		return errors.New("response body length differs from fixed Content-Length")
	}
	return r.forward("RESPONSE", metadata, body, destination)
}

func (r *OpaqueRelay) forward(direction string, metadata OuterMetadata, body []byte, destination io.Writer) error {
	// The relay performs one exact byte copy. It cannot decode, reconstruct,
	// translate, or re-encrypt the encapsulated OHTTP body.
	before := append([]byte(nil), body...)
	if _, err := io.CopyN(destination, bytes.NewReader(body), int64(len(body))); err != nil {
		return err
	}
	if !bytes.Equal(before, body) {
		return errors.New("relay input body was mutated")
	}
	r.Observations = append(r.Observations, RelayObservation{
		Direction: direction, RelayEndpoint: metadata.RelayEndpoint,
		GatewayEndpoint: metadata.GatewayEndpoint, ConnectionID: metadata.ConnectionID,
		ContentType: metadata.ContentType, ContentLength: metadata.ContentLength,
		Profile: metadata.Profile, Session: metadata.Slot.Session, Slot: metadata.Slot.Slot,
	})
	return nil
}
