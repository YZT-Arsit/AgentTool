package v7

import (
	"crypto/cipher"
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net"
	"os"

	gatewayv2 "common-action-gateway-v2"
)

const statusProfileOverflowByte byte = 6

type PacerConfig struct {
	Listen          string
	WireProfile     gatewayv2.PublicProfile
	Admission       AdmissionProfile
	RequestRingPath string
	ResultRingPath  string
	ReadyQueuePath  string
	WorkerDonePath  string
	KeyHex          string
	KeyFile         string
	HostLogPath     string
	PrivateLogPath  string
	LifecyclePath   string
	StatusPath      string
	CPU             int
	Realtime        bool
}

type PrivateDeliveryEvent struct {
	Session      uint32 `json:"session"`
	Slot         uint32 `json:"slot"`
	Status       byte   `json:"status"`
	OperationID  string `json:"operation_id,omitempty"`
	QueueDepth   int    `json:"queue_depth"`
	TerminalCode string `json:"terminal_code,omitempty"`
}

func RunPacer(config PacerConfig, ready func(string)) error {
	if err := config.Admission.Validate(); err != nil {
		return fmt.Errorf("admission profile: %w", err)
	}
	if config.Admission.TotalSlots() != config.WireProfile.Sessions*config.WireProfile.Slots {
		return fmt.Errorf("admission/wire profile frame counts differ")
	}
	isolation := gatewayv2.ApplyPacerIsolation(config.CPU, config.Realtime)
	requestRing, err := gatewayv2.OpenRing(config.RequestRingPath)
	if err != nil {
		return err
	}
	defer requestRing.Close()
	resultRing, err := gatewayv2.OpenRing(config.ResultRingPath)
	if err != nil {
		return err
	}
	defer resultRing.Close()
	readyQueue, err := OpenDurableReadyQueue(config.ReadyQueuePath, config.Admission.MaxRealOperations)
	if err != nil {
		return err
	}
	var aead cipher.AEAD
	if config.KeyFile != "" {
		aead, err = gatewayv2.ParseKeyFile(config.KeyFile)
	} else {
		aead, err = gatewayv2.ParseKey(config.KeyHex)
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
	transport := gatewayv2.NewTCPTransport(connection)
	defer transport.Close()

	total := config.Admission.TotalSlots()
	t0 := gatewayv2.MonotonicNowNS() + config.WireProfile.StartDelayNS
	handshake := make([]byte, 16)
	copy(handshake[:8], []byte("CAGV2T0!"))
	binary.BigEndian.PutUint64(handshake[8:], uint64(t0))
	if err := gatewayv2.WriteFixedFrame(connection, handshake); err != nil {
		return err
	}

	requestDiagnostics := gatewayv2.NewDiagnosticRing(total)
	responseDiagnostics := gatewayv2.NewDiagnosticRing(total)
	lifecycle := &LifecycleRecorder{}
	deliveries := make([]PrivateDeliveryEvent, 0, total)
	readerError := make(chan error, 1)
	requestSequence := gatewayv2.NewSequenceValidator(config.WireProfile.ID(), gatewayv2.DirectionRequest,
		config.WireProfile.Sessions, config.WireProfile.Slots)
	go func() {
		frame := make([]byte, config.WireProfile.FrameBytes)
		for index := 0; index < total; index++ {
			if err := transport.ReadFrame(frame); err != nil {
				readerError <- err
				return
			}
			received := gatewayv2.MonotonicNowNS()
			header, headerErr := gatewayv2.ParsePublicHeader(frame)
			if headerErr != nil || requestSequence.Accept(header) != nil {
				readerError <- fmt.Errorf("invalid public request sequence")
				return
			}
			if !requestRing.TryPush(frame) {
				readerError <- fmt.Errorf("request ring unexpectedly full")
				return
			}
			requestDiagnostics.Append(gatewayv2.TimingEvent{Direction: "REQUEST", Session: header.Session,
				Slot: header.Slot, ActualReceiveNS: received, FrameBytes: len(frame), Destination: "CommonActionGatewayV7"})
		}
		readerError <- nil
	}()

	frames := make([][]byte, total)
	nonces := make([][12]byte, total)
	for index := range frames {
		frames[index] = make([]byte, config.WireProfile.FrameBytes)
		if _, err := rand.Read(nonces[index][:]); err != nil {
			return err
		}
	}
	builder := gatewayv2.NewResponseFrameBuilder(aead, config.WireProfile.FrameBytes)
	resultBuffer := make([]byte, gatewayv2.InternalResultBytes)
	index := 0
	terminalStatus := "OK"
	for session := 0; session < config.WireProfile.Sessions; session++ {
		base := config.WireProfile.SessionBaseNS(t0, session)
		for slot := 1; slot <= config.WireProfile.Slots; slot++ {
			deadline := base + int64(slot)*config.WireProfile.ResponseDeltaNS
			cutoff := deadline - config.WireProfile.MaskNS
			gatewayv2.WaitUntilNS(cutoff)
			for resultRing.TryPop(resultBuffer) {
				candidate := gatewayv2.UnmarshalResult(resultBuffer)
				if _, err := readyQueue.Enqueue(candidate, gatewayv2.MonotonicNowNS()); err != nil {
					return err
				}
				lifecycle.Record(LifecycleEvent{OperationID: gatewayv2.OperationIDString(candidate.OperationID),
					Stage: StagePacerObserved, MonotonicNS: gatewayv2.MonotonicNowNS(),
					Session: uint32(session), Slot: uint32(slot)})
			}

			isTerminal := index >= total-config.Admission.TerminalSlots
			var selected *gatewayv2.ResultRecord
			if isTerminal {
				_, workerDoneErr := os.Stat(config.WorkerDonePath)
				if readyQueue.Pending() != 0 || resultRing.Depth() != 0 || workerDoneErr != nil {
					overflow := gatewayv2.ResultRecord{Status: statusProfileOverflowByte,
						OperationID: gatewayv2.OperationID("__gateway_profile_status__")}
					payload := []byte(StatusProfileOverflow)
					overflow.PayloadLen = uint16(len(payload))
					copy(overflow.Payload[:], payload)
					selected = &overflow
					terminalStatus = string(StatusProfileOverflow)
				}
			} else {
				selected, err = readyQueue.ReserveEligible(uint32(session), uint32(slot))
				if err != nil {
					return err
				}
			}
			if err := builder.Prepare(frames[index], nonces[index][:], config.WireProfile.ID(),
				uint32(session), uint32(slot), selected); err != nil {
				return err
			}
			prepared := gatewayv2.MonotonicNowNS()
			gatewayv2.WaitUntilNS(deadline)
			sendInvoked := gatewayv2.MonotonicNowNS()
			if err := transport.WriteFrame(frames[index]); err != nil {
				return err
			}
			responseDiagnostics.Append(gatewayv2.TimingEvent{Direction: "RESPONSE", Session: uint32(session),
				Slot: uint32(slot), ScheduledNS: deadline, CutoffNS: cutoff, PreparedNS: prepared,
				ActualSendNS: sendInvoked, FrameBytes: len(frames[index]), Destination: "CommonActionGatewayV7"})
			event := PrivateDeliveryEvent{Session: uint32(session), Slot: uint32(slot),
				Status: gatewayv2.StatusWait, QueueDepth: readyQueue.Pending()}
			if selected != nil {
				operationID := gatewayv2.OperationIDString(selected.OperationID)
				event.Status, event.OperationID = selected.Status, operationID
				if operationID == "__gateway_profile_status__" {
					event.TerminalCode = terminalStatus
				} else {
					if err := readyQueue.MarkDelivered(operationID); err != nil {
						return err
					}
					lifecycle.Record(LifecycleEvent{OperationID: operationID, Stage: StageResultCellSent,
						MonotonicNS: sendInvoked, Session: uint32(session), Slot: uint32(slot)})
				}
			}
			deliveries = append(deliveries, event)
			index++
		}
	}
	if err := <-readerError; err != nil {
		return err
	}
	if err := gatewayv2.DumpJSONL(config.HostLogPath, requestDiagnostics.Events(), responseDiagnostics.Events()); err != nil {
		return err
	}
	privateFile, err := os.Create(config.PrivateLogPath)
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(privateFile)
	for _, event := range deliveries {
		if err := encoder.Encode(event); err != nil {
			privateFile.Close()
			return err
		}
	}
	if err := privateFile.Close(); err != nil {
		return err
	}
	if config.LifecyclePath != "" {
		if err := lifecycle.DumpCSV(config.LifecyclePath); err != nil {
			return err
		}
	}
	statusArtifact := map[string]any{"pid": os.Getpid(), "isolation": isolation,
		"profile": config.WireProfile, "admission": config.Admission, "terminal_status": terminalStatus,
		"pending_results": readyQueue.Pending(), "provider_execution_in_pacer": false,
		"durable_ready_queue": true, "critical_path_logging": "PREALLOCATED_MEMORY_ONLY_EXCEPT_V7_DURABILITY_FSYNC"}
	raw, _ := json.MarshalIndent(statusArtifact, "", "  ")
	return os.WriteFile(config.StatusPath, raw, 0o600)
}
