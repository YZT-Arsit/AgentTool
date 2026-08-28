package gatewayv2

import (
	"crypto/cipher"
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net"
	"os"
)

type PacerConfig struct {
	Listen          string
	Profile         PublicProfile
	RequestRingPath string
	ResultRingPath  string
	KeyHex          string
	KeyFile         string
	HostLogPath     string
	PrivateLogPath  string
	StatusPath      string
	CPU             int
	Realtime        bool
}

type DeliveryEvent struct {
	Session     uint32 `json:"session"`
	Slot        uint32 `json:"slot"`
	Status      byte   `json:"status"`
	OperationID string `json:"operation_id,omitempty"`
	QueueDepth  uint64 `json:"queue_depth"`
}

type deliveryRecord struct {
	Session     uint32
	Slot        uint32
	Status      byte
	OperationID [OperationIDBytes]byte
	QueueDepth  uint64
}

func resultEligibleForPublicSession(requestSession, publicSession uint32) bool {
	return requestSession <= publicSession
}

func RunPacer(config PacerConfig, ready func(string)) error {
	status := ApplyPacerIsolation(config.CPU, config.Realtime)
	requestRing, err := OpenRing(config.RequestRingPath)
	if err != nil {
		return err
	}
	defer requestRing.Close()
	resultRing, err := OpenRing(config.ResultRingPath)
	if err != nil {
		return err
	}
	defer resultRing.Close()
	var aead cipher.AEAD
	if config.KeyFile != "" {
		aead, err = ParseKeyFile(config.KeyFile)
	} else {
		aead, err = ParseKey(config.KeyHex)
	}
	if err != nil {
		return err
	}
	listener, err := net.Listen("tcp", config.Listen)
	if err != nil {
		return err
	}
	defer listener.Close()
	ready(listener.Addr().String())
	connection, err := listener.Accept()
	if err != nil {
		return err
	}
	listener.Close()
	transport := NewTCPTransport(connection)
	defer transport.Close()

	total := config.Profile.Sessions * config.Profile.Slots
	if requestRing.Capacity() < total {
		return fmt.Errorf("request ring capacity %d is below public frame count %d", requestRing.Capacity(), total)
	}
	t0 := MonotonicNowNS() + config.Profile.StartDelayNS
	handshake := make([]byte, 16)
	copy(handshake[:8], []byte("CAGV2T0!"))
	binary.BigEndian.PutUint64(handshake[8:], uint64(t0))
	if err := WriteFixedFrame(connection, handshake); err != nil {
		return err
	}

	requestDiagnostics := NewDiagnosticRing(total)
	responseDiagnostics := NewDiagnosticRing(total)
	delivery := make([]deliveryRecord, 0, total)
	readerError := make(chan error, 1)
	requestSequence := NewSequenceValidator(config.Profile.ID(), DirectionRequest, config.Profile.Sessions, config.Profile.Slots)
	go func() {
		frame := make([]byte, config.Profile.FrameBytes)
		for index := 0; index < total; index++ {
			if err := transport.ReadFrame(frame); err != nil {
				readerError <- err
				return
			}
			received := MonotonicNowNS()
			header, headerErr := ParsePublicHeader(frame)
			if headerErr != nil || requestSequence.Accept(header) != nil {
				readerError <- fmt.Errorf("invalid public request sequence")
				return
			}
			session := header.Session
			slot := header.Slot
			if !requestRing.TryPush(frame) {
				readerError <- fmt.Errorf("request ring unexpectedly full")
				return
			}
			requestDiagnostics.Append(TimingEvent{Direction: "REQUEST", Session: session, Slot: slot,
				ActualReceiveNS: received, FrameBytes: len(frame), Destination: "CommonActionGatewayV2"})
		}
		readerError <- nil
	}()

	frames := make([][]byte, total)
	nonces := make([][nonceBytes]byte, total)
	for index := range frames {
		frames[index] = make([]byte, config.Profile.FrameBytes)
		if _, err := rand.Read(nonces[index][:]); err != nil {
			return err
		}
	}
	builder := NewResponseFrameBuilder(aead, config.Profile.FrameBytes)
	resultBuffer := make([]byte, InternalResultBytes)
	var pending ResultRecord
	hasPending := false
	index := 0
	for session := 0; session < config.Profile.Sessions; session++ {
		base := config.Profile.SessionBaseNS(t0, session)
		for slot := 1; slot <= config.Profile.Slots; slot++ {
			deadline := base + int64(slot)*config.Profile.ResponseDeltaNS
			cutoff := deadline - config.Profile.MaskNS
			WaitUntilNS(cutoff)
			var selected *ResultRecord
			if hasPending {
				// A private result that missed its request session remains eligible
				// for the next already-scheduled public response slot. It must not
				// be discarded and it must not extend the public schedule.
				if resultEligibleForPublicSession(pending.Session, uint32(session)) {
					selected = &pending
					hasPending = false
				}
			}
			if selected == nil && !hasPending && resultRing.TryPop(resultBuffer) {
				candidate := UnmarshalResult(resultBuffer)
				if resultEligibleForPublicSession(candidate.Session, uint32(session)) {
					pending = candidate
					selected = &pending
				} else if candidate.Session > uint32(session) {
					pending = candidate
					hasPending = true
				}
			}
			if err := builder.Prepare(frames[index], nonces[index][:], config.Profile.ID(), uint32(session), uint32(slot), selected); err != nil {
				return err
			}
			prepared := MonotonicNowNS()
			WaitUntilNS(deadline)
			sendInvoked := MonotonicNowNS()
			if err := transport.WriteFrame(frames[index]); err != nil {
				return err
			}
			responseDiagnostics.Append(TimingEvent{Direction: "RESPONSE", Session: uint32(session), Slot: uint32(slot),
				ScheduledNS: deadline, CutoffNS: cutoff, PreparedNS: prepared, ActualSendNS: sendInvoked,
				FrameBytes: len(frames[index]), Destination: "CommonActionGatewayV2"})
			deliveryEvent := deliveryRecord{Session: uint32(session), Slot: uint32(slot), Status: StatusWait,
				QueueDepth: resultRing.Depth()}
			if selected != nil {
				deliveryEvent.Status = selected.Status
				deliveryEvent.OperationID = selected.OperationID
			}
			delivery = append(delivery, deliveryEvent)
			index++
		}
	}
	if err := <-readerError; err != nil {
		return err
	}
	if err := DumpJSONL(config.HostLogPath, requestDiagnostics.Events(), responseDiagnostics.Events()); err != nil {
		return err
	}
	privateFile, err := os.Create(config.PrivateLogPath)
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(privateFile)
	for _, event := range delivery {
		serialized := DeliveryEvent{Session: event.Session, Slot: event.Slot, Status: event.Status,
			OperationID: OperationIDString(event.OperationID), QueueDepth: event.QueueDepth}
		if err := encoder.Encode(serialized); err != nil {
			privateFile.Close()
			return err
		}
	}
	if err := privateFile.Close(); err != nil {
		return err
	}
	statusArtifact := map[string]any{
		"pid": os.Getpid(), "isolation": status, "tcp": TCPTransmitCapability(),
		"timed_datagram": FutureTimedDatagramCapability(), "profile": config.Profile,
		"critical_path_logging": "PREALLOCATED_MEMORY_ONLY", "provider_execution_in_pacer": false,
	}
	raw, _ := json.MarshalIndent(statusArtifact, "", "  ")
	if err := os.WriteFile(config.StatusPath, raw, 0o600); err != nil {
		return err
	}
	if len(responseDiagnostics.Events()) != total {
		return fmt.Errorf("sent %d frames, expected %d", len(responseDiagnostics.Events()), total)
	}
	return nil
}
