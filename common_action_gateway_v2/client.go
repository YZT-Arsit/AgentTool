package gatewayv2

import (
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"sync"
)

type WorkloadAction struct {
	Action      string `json:"action"`
	Provider    string `json:"provider"`
	OperationID string `json:"operation_id"`
	Payload     string `json:"payload,omitempty"`
}

type WorkloadSession struct {
	Label   string           `json:"label"`
	Actions []WorkloadAction `json:"actions"`
}

type PrivateWorkload struct {
	Sessions []WorkloadSession `json:"sessions"`
}

func LoadWorkload(path string) (PrivateWorkload, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return PrivateWorkload{}, err
	}
	var workload PrivateWorkload
	if err := json.Unmarshal(raw, &workload); err != nil {
		return PrivateWorkload{}, err
	}
	return workload, nil
}

func actionCode(value string) byte {
	switch value {
	case "TOOL":
		return ActionTool
	case "LLM":
		return ActionLLM
	case "AGENT":
		return ActionAgent
	default:
		return ActionNoop
	}
}

func providerCode(value string) byte {
	switch value {
	case "FAST":
		return ProviderFast
	case "MEDIUM":
		return ProviderMedium
	case "SLOW":
		return ProviderSlow
	case "VERY_SLOW":
		return ProviderVerySlow
	case "JITTERED":
		return ProviderJittered
	default:
		return ProviderNone
	}
}

type ClientConfig struct {
	Address     string
	Profile     PublicProfile
	Workload    PrivateWorkload
	KeyHex      string
	HostLogPath string
	CPU         int
}

func RunCloudClient(config ClientConfig) error {
	_ = ApplyWorkerAffinity(config.CPU)
	if len(config.Workload.Sessions) != config.Profile.Sessions {
		return fmt.Errorf("workload has %d sessions, profile requires %d", len(config.Workload.Sessions), config.Profile.Sessions)
	}
	aead, err := ParseKey(config.KeyHex)
	if err != nil {
		return err
	}
	total := config.Profile.Sessions * config.Profile.Slots
	frames := make([][]byte, total)
	index := 0
	for session, workloadSession := range config.Workload.Sessions {
		if len(workloadSession.Actions) > config.Profile.Slots {
			return fmt.Errorf("session %d exceeds public horizon", session)
		}
		for slot := 1; slot <= config.Profile.Slots; slot++ {
			action := WorkloadAction{Action: "NOOP", Provider: "NONE", OperationID: fmt.Sprintf("pad-%d-%d", session, slot)}
			if slot <= len(workloadSession.Actions) {
				action = workloadSession.Actions[slot-1]
			}
			frame := make([]byte, config.Profile.FrameBytes)
			nonce := make([]byte, nonceBytes)
			if _, err := rand.Read(nonce); err != nil {
				return err
			}
			op := PrivateOperation{Session: uint32(session), Slot: uint32(slot), Action: actionCode(action.Action),
				Provider: providerCode(action.Provider), OperationID: OperationID(action.OperationID), Payload: []byte(action.Payload)}
			if err := EncodeRequest(aead, frame, nonce, config.Profile.ID(), op); err != nil {
				return err
			}
			frames[index] = frame
			index++
		}
	}
	connection, err := net.Dial("tcp", config.Address)
	if err != nil {
		return err
	}
	transport := NewTCPTransport(connection)
	defer transport.Close()
	handshake := make([]byte, 16)
	if err := ReadFixedFrame(connection, handshake); err != nil {
		return err
	}
	if string(handshake[:8]) != "CAGV2T0!" {
		return fmt.Errorf("invalid public handshake")
	}
	t0 := int64(binary.BigEndian.Uint64(handshake[8:]))
	requestDiagnostics := NewDiagnosticRing(total)
	responseDiagnostics := NewDiagnosticRing(total)
	var receiveErr error
	var receiver sync.WaitGroup
	receiver.Add(1)
	go func() {
		defer receiver.Done()
		frame := make([]byte, config.Profile.FrameBytes)
		for responseIndex := 0; responseIndex < total; responseIndex++ {
			if err := transport.ReadFrame(frame); err != nil {
				receiveErr = err
				return
			}
			received := MonotonicNowNS()
			responseDiagnostics.Append(TimingEvent{Direction: "RESPONSE", Session: binary.BigEndian.Uint32(frame[0:4]),
				Slot: binary.BigEndian.Uint32(frame[4:8]), ActualReceiveNS: received,
				FrameBytes: len(frame), Destination: "CommonActionGatewayV2"})
		}
	}()
	index = 0
	for session := 0; session < config.Profile.Sessions; session++ {
		base := config.Profile.SessionBaseNS(t0, session)
		for slot := 1; slot <= config.Profile.Slots; slot++ {
			deadline := base + int64(slot)*config.Profile.RequestDeltaNS
			WaitUntilNS(deadline)
			sendInvoked := MonotonicNowNS()
			if err := transport.WriteFrame(frames[index]); err != nil {
				return err
			}
			requestDiagnostics.Append(TimingEvent{Direction: "REQUEST", Session: uint32(session), Slot: uint32(slot),
				ScheduledNS: deadline, ActualSendNS: sendInvoked, FrameBytes: len(frames[index]),
				Destination: "CommonActionGatewayV2"})
			index++
		}
	}
	receiver.Wait()
	if receiveErr != nil {
		return receiveErr
	}
	return DumpJSONL(config.HostLogPath, requestDiagnostics.Events(), responseDiagnostics.Events())
}
