package v7ohttp

// PrivateResponse is the application plaintext that will eventually be
// encoded as fixed padded BHTTP and encapsulated with this slot's response
// context. OperationID can refer to an operation admitted in an earlier slot.
type PrivateResponse struct {
	Status      byte
	OperationID string
	Payload     []byte
}

type SlotResponse struct {
	ContextSlot SlotID
	Result      *PrivateResponse
}

func SelectForSlot(contextSlot SlotID, result *PrivateResponse) SlotResponse {
	return SlotResponse{ContextSlot: contextSlot, Result: result}
}
