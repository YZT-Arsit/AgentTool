package v7ohttp

// LegacyDevTransport records the status of the frozen custom AES-GCM framing.
// It deliberately does not implement ClientBackend or GatewayBackend, so it
// cannot be wired into the canonical V7-OHTTP path by interface substitution.
type LegacyDevTransport struct{}

func (LegacyDevTransport) Name() string      { return "LEGACY_DEV_TRANSPORT" }
func (LegacyDevTransport) RFC9458Wire() bool { return false }
func (LegacyDevTransport) Canonical() bool   { return false }
