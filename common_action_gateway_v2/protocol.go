package gatewayv2

import (
	"crypto/aes"
	"crypto/cipher"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
)

const (
	ActionNoop  byte = 0
	ActionTool  byte = 1
	ActionLLM   byte = 2
	ActionAgent byte = 3

	StatusWait      byte = 0
	StatusOK        byte = 1
	StatusError     byte = 2
	StatusTimeout   byte = 3
	StatusCancelled byte = 4

	ProviderNone     byte = 0
	ProviderFast     byte = 1
	ProviderMedium   byte = 2
	ProviderSlow     byte = 3
	ProviderVerySlow byte = 4
	ProviderJittered byte = 5

	InternalResultBytes = 768
	OperationIDBytes    = 32
	ResultPayloadBytes  = InternalResultBytes - 48
	requestHeaderBytes  = 12
	nonceBytes          = 12
)

var requestAAD = []byte("COMMON_ACTION_GATEWAY_V2_REQUEST")
var responseAAD = []byte("COMMON_ACTION_GATEWAY_V2_RESPONSE")

type PrivateOperation struct {
	Session     uint32
	Slot        uint32
	Action      byte
	Provider    byte
	OperationID [OperationIDBytes]byte
	Payload     []byte
}

type ResultRecord struct {
	Session     uint32
	RequestSlot uint32
	Status      byte
	OperationID [OperationIDBytes]byte
	PayloadLen  uint16
	Payload     [ResultPayloadBytes]byte
}

func ParseKey(value string) (cipher.AEAD, error) {
	key, err := hex.DecodeString(value)
	if err != nil {
		return nil, err
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	return cipher.NewGCM(block)
}

func OperationID(value string) [OperationIDBytes]byte {
	var result [OperationIDBytes]byte
	copy(result[:], []byte(value))
	return result
}

func OperationIDString(value [OperationIDBytes]byte) string {
	end := len(value)
	for end > 0 && value[end-1] == 0 {
		end--
	}
	return string(value[:end])
}

func EncodeRequest(aead cipher.AEAD, frame []byte, nonce []byte, op PrivateOperation) error {
	if len(frame) < requestHeaderBytes+nonceBytes+aead.Overhead()+42 {
		return errors.New("request frame too small")
	}
	if len(nonce) != nonceBytes {
		return errors.New("invalid nonce")
	}
	plainBytes := len(frame) - requestHeaderBytes - nonceBytes - aead.Overhead()
	plain := make([]byte, plainBytes)
	plain[0] = op.Action
	plain[1] = op.Provider
	binary.BigEndian.PutUint16(plain[2:4], uint16(len(op.Payload)))
	copy(plain[4:4+OperationIDBytes], op.OperationID[:])
	if len(op.Payload) > len(plain)-36 {
		return errors.New("request payload overflow")
	}
	copy(plain[36:], op.Payload)
	binary.BigEndian.PutUint32(frame[0:4], op.Session)
	binary.BigEndian.PutUint32(frame[4:8], op.Slot)
	binary.BigEndian.PutUint32(frame[8:12], 2)
	copy(frame[12:24], nonce)
	sealed := aead.Seal(frame[:24], nonce, plain, requestAAD)
	if len(sealed) != len(frame) {
		return errors.New("unexpected request ciphertext size")
	}
	return nil
}

func DecodeRequest(aead cipher.AEAD, frame []byte) (PrivateOperation, error) {
	if len(frame) < 64 {
		return PrivateOperation{}, errors.New("short request")
	}
	plain, err := aead.Open(nil, frame[12:24], frame[24:], requestAAD)
	if err != nil {
		return PrivateOperation{}, err
	}
	payloadLen := int(binary.BigEndian.Uint16(plain[2:4]))
	if payloadLen > len(plain)-36 {
		return PrivateOperation{}, errors.New("invalid payload length")
	}
	result := PrivateOperation{
		Session:  binary.BigEndian.Uint32(frame[0:4]),
		Slot:     binary.BigEndian.Uint32(frame[4:8]),
		Action:   plain[0],
		Provider: plain[1],
		Payload:  append([]byte(nil), plain[36:36+payloadLen]...),
	}
	copy(result.OperationID[:], plain[4:36])
	return result, nil
}

func MarshalResult(dst []byte, record ResultRecord) {
	if len(dst) != InternalResultBytes {
		panic("invalid result record buffer")
	}
	clear(dst)
	binary.BigEndian.PutUint32(dst[0:4], record.Session)
	binary.BigEndian.PutUint32(dst[4:8], record.RequestSlot)
	dst[8] = record.Status
	binary.BigEndian.PutUint16(dst[10:12], record.PayloadLen)
	copy(dst[16:48], record.OperationID[:])
	copy(dst[48:], record.Payload[:])
}

func UnmarshalResult(src []byte) ResultRecord {
	if len(src) != InternalResultBytes {
		panic("invalid result record")
	}
	var result ResultRecord
	result.Session = binary.BigEndian.Uint32(src[0:4])
	result.RequestSlot = binary.BigEndian.Uint32(src[4:8])
	result.Status = src[8]
	result.PayloadLen = binary.BigEndian.Uint16(src[10:12])
	copy(result.OperationID[:], src[16:48])
	copy(result.Payload[:], src[48:])
	return result
}

type ResponseFrameBuilder struct {
	aead      cipher.AEAD
	frameSize int
	plain     []byte
}

func NewResponseFrameBuilder(aead cipher.AEAD, frameSize int) *ResponseFrameBuilder {
	plainBytes := frameSize - requestHeaderBytes - nonceBytes - aead.Overhead()
	return &ResponseFrameBuilder{aead: aead, frameSize: frameSize, plain: make([]byte, plainBytes)}
}

func (b *ResponseFrameBuilder) Prepare(dst, nonce []byte, session, slot uint32, record *ResultRecord) error {
	if len(dst) != b.frameSize || len(nonce) != nonceBytes {
		return errors.New("invalid response buffers")
	}
	clear(b.plain)
	if record != nil {
		b.plain[0] = record.Status
		copy(b.plain[4:36], record.OperationID[:])
		binary.BigEndian.PutUint16(b.plain[36:38], record.PayloadLen)
		copy(b.plain[48:], record.Payload[:])
	}
	binary.BigEndian.PutUint32(dst[0:4], session)
	binary.BigEndian.PutUint32(dst[4:8], slot)
	binary.BigEndian.PutUint32(dst[8:12], 2)
	copy(dst[12:24], nonce)
	sealed := b.aead.Seal(dst[:24], nonce, b.plain, responseAAD)
	if len(sealed) != len(dst) {
		return fmt.Errorf("unexpected response size %d", len(sealed))
	}
	return nil
}

func ReadFixedFrame(reader io.Reader, frame []byte) error {
	_, err := io.ReadFull(reader, frame)
	return err
}

func WriteFixedFrame(writer io.Writer, frame []byte) error {
	for len(frame) > 0 {
		written, err := writer.Write(frame)
		if err != nil {
			return err
		}
		frame = frame[written:]
	}
	return nil
}
