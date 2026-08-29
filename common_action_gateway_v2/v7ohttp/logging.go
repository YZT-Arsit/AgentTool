package v7ohttp

// PublicExperimentEvent is the only Relay-side experiment record. It contains
// public profile and transport measurements, never application semantics.
type PublicExperimentEvent struct {
	ProfileID           string `json:"profile_id"`
	Session             uint32 `json:"session"`
	Round               uint32 `json:"round"`
	OuterRequestLength  int    `json:"outer_request_length"`
	OuterResponseLength int    `json:"outer_response_length"`
	RelayEndpoint       string `json:"relay_endpoint"`
	GatewayEndpoint     string `json:"gateway_endpoint"`
	ConnectionID        string `json:"connection_id"`
	RequestObservedNS   int64  `json:"request_observed_ns"`
	ResponseObservedNS  int64  `json:"response_observed_ns"`
}

// PrivateCorrectnessEvent belongs only to trusted correctness logs. It is a
// separate type so private labels cannot be accidentally appended to public
// Relay records.
type PrivateCorrectnessEvent struct {
	OperationID    string `json:"operation_id"`
	ActionClass    string `json:"action_class"`
	LocalEmulator  string `json:"local_emulator"`
	LifecycleState string `json:"lifecycle_state"`
	ResultStatus   string `json:"result_status"`
}
