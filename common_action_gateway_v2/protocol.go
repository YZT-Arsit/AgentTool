package gatewayv2

import (
	"crypto/aes"
	"crypto/cipher"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
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
	StatusAmbiguous byte = 5

	ProviderNone       byte = 0
	ProviderFast       byte = 1
	ProviderMedium     byte = 2
	ProviderSlow       byte = 3
	ProviderVerySlow   byte = 4
	ProviderJittered   byte = 5
	ProviderLocalModel byte = 6
	ProviderReadOnly   byte = 7
	ProviderEffectful  byte = 8

	InternalResultBytes = 768
	OperationIDBytes    = 32
	ResultPayloadBytes  = InternalResultBytes - 48
	ProtocolVersion     = uint16(3)
	DirectionRequest    = byte(1)
	DirectionResponse   = byte(2)
	PublicHeaderBytes   = 20
	nonceBytes          = 12
)

type PublicFrameHeader struct {
	Version   uint16
	Direction byte
	Session   uint32
	Slot      uint32
	ProfileID uint64
}

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

func ParseKeyFile(path string) (cipher.AEAD, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return ParseKey(strings.TrimSpace(string(raw)))
}

func marshalPublicHeader(dst []byte, header PublicFrameHeader) error {
	if len(dst) < PublicHeaderBytes {
		return errors.New("short public frame header")
	}
	if header.Version != ProtocolVersion {
		return fmt.Errorf("unsupported protocol version %d", header.Version)
	}
	if header.Direction != DirectionRequest && header.Direction != DirectionResponse {
		return errors.New("invalid frame direction")
	}
	binary.BigEndian.PutUint16(dst[0:2], header.Version)
	dst[2] = header.Direction
	dst[3] = 0
	binary.BigEndian.PutUint32(dst[4:8], header.Session)
	binary.BigEndian.PutUint32(dst[8:12], header.Slot)
	binary.BigEndian.PutUint64(dst[12:20], header.ProfileID)
	return nil
}

func ParsePublicHeader(frame []byte) (PublicFrameHeader, error) {
	if len(frame) < PublicHeaderBytes+nonceBytes+16 {
		return PublicFrameHeader{}, errors.New("short frame")
	}
	header := PublicFrameHeader{
		Version: binary.BigEndian.Uint16(frame[0:2]), Direction: frame[2],
		Session: binary.BigEndian.Uint32(frame[4:8]), Slot: binary.BigEndian.Uint32(frame[8:12]),
		ProfileID: binary.BigEndian.Uint64(frame[12:20]),
	}
	if frame[3] != 0 {
		return PublicFrameHeader{}, errors.New("nonzero reserved header byte")
	}
	if header.Version != ProtocolVersion {
		return PublicFrameHeader{}, fmt.Errorf("unsupported protocol version %d", header.Version)
	}
	if header.Direction != DirectionRequest && header.Direction != DirectionResponse {
		return PublicFrameHeader{}, errors.New("invalid frame direction")
	}
	return header, nil
}

type SequenceValidator struct {
	ProfileID uint64
	Direction byte
	Sessions  uint32
	Slots     uint32
	next      uint64
}

func NewSequenceValidator(profileID uint64, direction byte, sessions, slots int) *SequenceValidator {
	return &SequenceValidator{ProfileID: profileID, Direction: direction, Sessions: uint32(sessions), Slots: uint32(slots)}
}

func (v *SequenceValidator) Accept(header PublicFrameHeader) error {
	if header.ProfileID != v.ProfileID || header.Direction != v.Direction {
		return errors.New("frame profile/direction mismatch")
	}
	if header.Session >= v.Sessions || header.Slot < 1 || header.Slot > v.Slots {
		return errors.New("frame session/slot out of range")
	}
	expectedSession := uint32(v.next / uint64(v.Slots))
	expectedSlot := uint32(v.next%uint64(v.Slots)) + 1
	if header.Session != expectedSession || header.Slot != expectedSlot {
		return fmt.Errorf("duplicate, replayed, or non-monotonic frame: got %d/%d want %d/%d",
			header.Session, header.Slot, expectedSession, expectedSlot)
	}
	v.next++
	return nil
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

func EncodeRequest(aead cipher.AEAD, frame []byte, nonce []byte, profileID uint64, op PrivateOperation) error {
	if len(frame) < PublicHeaderBytes+nonceBytes+aead.Overhead()+42 {
		return errors.New("request frame too small")
	}
	if len(nonce) != nonceBytes {
		return errors.New("invalid nonce")
	}
	plainBytes := len(frame) - PublicHeaderBytes - nonceBytes - aead.Overhead()
	plain := make([]byte, plainBytes)
	plain[0] = op.Action
	plain[1] = op.Provider
	binary.BigEndian.PutUint16(plain[2:4], uint16(len(op.Payload)))
	copy(plain[4:4+OperationIDBytes], op.OperationID[:])
	if len(op.Payload) > len(plain)-36 {
		return errors.New("request payload overflow")
	}
	copy(plain[36:], op.Payload)
	header := PublicFrameHeader{Version: ProtocolVersion, Direction: DirectionRequest,
		Session: op.Session, Slot: op.Slot, ProfileID: profileID}
	if err := marshalPublicHeader(frame[:PublicHeaderBytes], header); err != nil {
		return err
	}
	copy(frame[PublicHeaderBytes:PublicHeaderBytes+nonceBytes], nonce)
	prefix := PublicHeaderBytes + nonceBytes
	sealed := aead.Seal(frame[:prefix], nonce, plain, frame[:PublicHeaderBytes])
	if len(sealed) != len(frame) {
		return errors.New("unexpected request ciphertext size")
	}
	return nil
}

func DecodeRequest(aead cipher.AEAD, frame []byte, expectedProfileID uint64) (PrivateOperation, error) {
	if len(frame) < 64 {
		return PrivateOperation{}, errors.New("short request")
	}
	header, err := ParsePublicHeader(frame)
	if err != nil {
		return PrivateOperation{}, err
	}
	if header.Direction != DirectionRequest || header.ProfileID != expectedProfileID {
		return PrivateOperation{}, errors.New("request profile/direction mismatch")
	}
	prefix := PublicHeaderBytes + nonceBytes
	plain, err := aead.Open(nil, frame[PublicHeaderBytes:prefix], frame[prefix:], frame[:PublicHeaderBytes])
	if err != nil {
		return PrivateOperation{}, err
	}
	payloadLen := int(binary.BigEndian.Uint16(plain[2:4]))
	if payloadLen > len(plain)-36 {
		return PrivateOperation{}, errors.New("invalid payload length")
	}
	result := PrivateOperation{
		Session:  header.Session,
		Slot:     header.Slot,
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
	plainBytes := frameSize - PublicHeaderBytes - nonceBytes - aead.Overhead()
	return &ResponseFrameBuilder{aead: aead, frameSize: frameSize, plain: make([]byte, plainBytes)}
}

func (b *ResponseFrameBuilder) Prepare(dst, nonce []byte, profileID uint64, session, slot uint32, record *ResultRecord) error {
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
	header := PublicFrameHeader{Version: ProtocolVersion, Direction: DirectionResponse,
		Session: session, Slot: slot, ProfileID: profileID}
	if err := marshalPublicHeader(dst[:PublicHeaderBytes], header); err != nil {
		return err
	}
	copy(dst[PublicHeaderBytes:PublicHeaderBytes+nonceBytes], nonce)
	prefix := PublicHeaderBytes + nonceBytes
	sealed := b.aead.Seal(dst[:prefix], nonce, b.plain, dst[:PublicHeaderBytes])
	if len(sealed) != len(dst) {
		return fmt.Errorf("unexpected response size %d", len(sealed))
	}
	return nil
}

func DecodeResponse(aead cipher.AEAD, frame []byte, expectedProfileID uint64) (PublicFrameHeader, *ResultRecord, error) {
	header, err := ParsePublicHeader(frame)
	if err != nil {
		return PublicFrameHeader{}, nil, err
	}
	if header.Direction != DirectionResponse || header.ProfileID != expectedProfileID {
		return PublicFrameHeader{}, nil, errors.New("response profile/direction mismatch")
	}
	prefix := PublicHeaderBytes + nonceBytes
	plain, err := aead.Open(nil, frame[PublicHeaderBytes:prefix], frame[prefix:], frame[:PublicHeaderBytes])
	if err != nil {
		return PublicFrameHeader{}, nil, err
	}
	if len(plain) < 48 {
		return PublicFrameHeader{}, nil, errors.New("short response plaintext")
	}
	if plain[0] == StatusWait {
		return header, nil, nil
	}
	payloadLen := binary.BigEndian.Uint16(plain[36:38])
	if int(payloadLen) > len(plain)-48 || int(payloadLen) > ResultPayloadBytes {
		return PublicFrameHeader{}, nil, errors.New("invalid response payload length")
	}
	record := &ResultRecord{Session: header.Session, RequestSlot: header.Slot,
		Status: plain[0], PayloadLen: payloadLen}
	copy(record.OperationID[:], plain[4:36])
	copy(record.Payload[:], plain[48:48+int(payloadLen)])
	return header, record, nil
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
