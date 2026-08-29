package v7ohttp

import "fmt"

type SlotID struct {
	Session uint32
	Slot    uint32
}

type PublicProfile struct {
	Name                      string
	Sessions                  uint32
	SlotsPerSession           uint32
	RequestEncapsulatedBytes  int
	ResponseEncapsulatedBytes int
	RequestDeltaNS            int64
	ResponseLagNS             int64
	PublicLifetimeNS          int64
}

func (p PublicProfile) Validate() error {
	if p.Name == "" || p.Sessions == 0 || p.SlotsPerSession == 0 {
		return fmt.Errorf("invalid public slot dimensions")
	}
	if p.RequestEncapsulatedBytes <= 0 || p.ResponseEncapsulatedBytes <= 0 {
		return fmt.Errorf("fixed encapsulated lengths are required")
	}
	if p.RequestDeltaNS <= 0 || p.ResponseLagNS <= 0 || p.PublicLifetimeNS <= 0 {
		return fmt.Errorf("public timing profile is incomplete")
	}
	return nil
}

func (p PublicProfile) Exchanges() uint64 {
	return uint64(p.Sessions) * uint64(p.SlotsPerSession)
}

type OuterMetadata struct {
	RelayEndpoint   string
	GatewayEndpoint string
	ConnectionID    string
	ContentType     string
	ContentLength   int
	Profile         string
	Slot            SlotID
}

func ValidateRequestMetadata(profile PublicProfile, metadata OuterMetadata) error {
	if metadata.ContentType != RequestContentType || metadata.ContentLength != profile.RequestEncapsulatedBytes {
		return fmt.Errorf("request outer metadata does not match public profile")
	}
	if metadata.Profile != profile.Name || metadata.RelayEndpoint == "" || metadata.GatewayEndpoint == "" || metadata.ConnectionID == "" {
		return fmt.Errorf("request outer route/profile is incomplete")
	}
	return nil
}

func ValidateResponseMetadata(profile PublicProfile, metadata OuterMetadata) error {
	if metadata.ContentType != ResponseContentType || metadata.ContentLength != profile.ResponseEncapsulatedBytes {
		return fmt.Errorf("response outer metadata does not match public profile")
	}
	if metadata.Profile != profile.Name || metadata.RelayEndpoint == "" || metadata.GatewayEndpoint == "" || metadata.ConnectionID == "" {
		return fmt.Errorf("response outer route/profile is incomplete")
	}
	return nil
}
