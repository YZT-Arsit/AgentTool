package main

import (
	"bufio"
	"crypto/aes"
	"crypto/cipher"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

const requestAAD = "ACV_TIMING_REQ_V1"
const responseAAD = "ACV_TIMING_RESP_V1"

type workload struct {
	FrameBytes     int       `json:"frame_bytes"`
	DeltaNS        int64     `json:"delta_ns"`
	ResponseLagNS  int64     `json:"response_lag_ns"`
	StartDelayNS   int64     `json:"start_delay_ns"`
	InterEpisodeNS int64     `json:"inter_episode_ns"`
	PublicProfile  string    `json:"public_profile"`
	Episodes       []episode `json:"episodes"`
}

type episode struct {
	Token  uint64   `json:"token"`
	Frames []string `json:"frames_base64"`
}

type privateRequest struct {
	EpisodeToken uint64  `json:"episode_token"`
	Slot         int     `json:"slot"`
	Action       string  `json:"action"`
	Provider     string  `json:"provider"`
	LatencyMS    float64 `json:"latency_ms"`
	OperationID  string  `json:"operation_id"`
}

type responseJob struct {
	Deadline int64
	Episode  uint64
	Slot     int
}

type resultState struct {
	ReadyCount    atomic.Int64
	ReleasedCount atomic.Int64
	EffectCount   atomic.Int64
}

type jsonWriter struct {
	mu sync.Mutex
	w  *bufio.Writer
}

func (w *jsonWriter) write(value any) {
	w.mu.Lock()
	defer w.mu.Unlock()
	b, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	if _, err := w.w.Write(append(b, '\n')); err != nil {
		panic(err)
	}
	if err := w.w.Flush(); err != nil {
		panic(err)
	}
}

func waitUntil(deadline int64) int64 {
	for {
		now := time.Now().UnixNano()
		remaining := deadline - now
		if remaining <= 0 {
			return now
		}
		if remaining > 2_000_000 {
			time.Sleep(time.Duration(remaining - 1_000_000))
		} else {
			runtimeYield()
		}
	}
}

func runtimeYield() { time.Sleep(0) }

func readFrame(conn net.Conn, size int) ([]byte, error) {
	header := make([]byte, 4)
	if _, err := io.ReadFull(conn, header); err != nil {
		return nil, err
	}
	if int(binary.BigEndian.Uint32(header)) != size {
		return nil, fmt.Errorf("unexpected frame size")
	}
	frame := make([]byte, size)
	_, err := io.ReadFull(conn, frame)
	return frame, err
}

func writeFrame(conn net.Conn, frame []byte) error {
	header := make([]byte, 4)
	binary.BigEndian.PutUint32(header, uint32(len(frame)))
	if _, err := conn.Write(header); err != nil {
		return err
	}
	_, err := conn.Write(frame)
	return err
}

func decryptRequest(aead cipher.AEAD, frame []byte) privateRequest {
	if len(frame) < 20 {
		panic("short request frame")
	}
	plaintext, err := aead.Open(nil, frame[8:20], frame[20:], []byte(requestAAD))
	if err != nil {
		panic(err)
	}
	var request privateRequest
	end := len(plaintext)
	for end > 0 && plaintext[end-1] == 0 {
		end--
	}
	if err := json.Unmarshal(plaintext[:end], &request); err != nil {
		panic(err)
	}
	return request
}

func encryptResponse(aead cipher.AEAD, frameBytes int, episode uint64, slot int, kind string) []byte {
	headerBytes := 12
	nonceBytes := aead.NonceSize()
	plainBytes := frameBytes - headerBytes - nonceBytes - aead.Overhead()
	payload, _ := json.Marshal(map[string]any{"kind": kind})
	if len(payload) > plainBytes {
		panic("response overflow")
	}
	plain := make([]byte, plainBytes)
	copy(plain, payload)
	nonce := make([]byte, nonceBytes)
	if _, err := io.ReadFull(randReader{}, nonce); err != nil {
		panic(err)
	}
	frame := make([]byte, headerBytes+nonceBytes)
	binary.BigEndian.PutUint64(frame[0:8], episode)
	binary.BigEndian.PutUint32(frame[8:12], uint32(slot))
	copy(frame[12:], nonce)
	return append(frame, aead.Seal(nil, nonce, plain, []byte(responseAAD))...)
}

// randReader avoids a package-global test hook and delegates to the OS on each frame.
type randReader struct{}

func (randReader) Read(p []byte) (int, error) {
	f, err := os.Open("/dev/urandom")
	if err == nil {
		defer f.Close()
		return io.ReadFull(f, p)
	}
	// Windows has no /dev/urandom; crypto/rand is used through this fallback.
	return cryptoRandRead(p)
}

func cryptoRandRead(p []byte) (int, error) { return readCryptoRandom(p) }

func runGateway(port int, keyHex, hostPath, privatePath string, frameBytes int) {
	key, err := hex.DecodeString(keyHex)
	if err != nil {
		panic(err)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		panic(err)
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		panic(err)
	}
	hostFile, _ := os.Create(hostPath)
	defer hostFile.Close()
	privateFile, _ := os.Create(privatePath)
	defer privateFile.Close()
	host := &jsonWriter{w: bufio.NewWriter(hostFile)}
	private := &jsonWriter{w: bufio.NewWriter(privateFile)}

	listener, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		panic(err)
	}
	fmt.Printf("READY %s\n", listener.Addr().String())
	conn, err := listener.Accept()
	if err != nil {
		panic(err)
	}
	listener.Close()
	defer conn.Close()
	if tcp, ok := conn.(*net.TCPConn); ok {
		tcp.SetNoDelay(true)
	}

	jobs := make(chan responseJob, 1024)
	states := sync.Map{}
	var writeMu sync.Mutex
	done := make(chan struct{})
	go func() {
		for job := range jobs {
			actual := waitUntil(job.Deadline)
			kind := "WAIT"
			if value, ok := states.Load(job.Episode); ok {
				state := value.(*resultState)
				ready := state.ReadyCount.Load()
				released := state.ReleasedCount.Load()
				if ready > released && state.ReleasedCount.CompareAndSwap(released, released+1) {
					kind = "REAL_RESULT"
				}
			}
			frame := encryptResponse(aead, frameBytes, job.Episode, job.Slot, kind)
			writeMu.Lock()
			err := writeFrame(conn, frame)
			writeMu.Unlock()
			if err != nil {
				break
			}
			host.write(map[string]any{"episode_token": job.Episode, "slot": job.Slot,
				"gateway_response_scheduled_ns": job.Deadline, "gateway_response_send_ns": actual,
				"response_bytes": frameBytes, "destination": "CommonActionGateway"})
			private.write(map[string]any{"episode_token": job.Episode, "slot": job.Slot,
				"private_response_kind": kind})
		}
		close(done)
	}()

	for {
		frame, err := readFrame(conn, frameBytes)
		if err == io.EOF || err == io.ErrUnexpectedEOF {
			break
		}
		if err != nil {
			panic(err)
		}
		received := time.Now().UnixNano()
		deadline := int64(binary.BigEndian.Uint64(frame[0:8]))
		request := decryptRequest(aead, frame)
		host.write(map[string]any{"episode_token": request.EpisodeToken, "slot": request.Slot,
			"gateway_request_receive_ns": received, "request_bytes": frameBytes,
			"destination": "CommonActionGateway"})
		stateValue, _ := states.LoadOrStore(request.EpisodeToken, &resultState{})
		state := stateValue.(*resultState)
		private.write(map[string]any{"episode_token": request.EpisodeToken, "slot": request.Slot,
			"private_action": request.Action, "private_provider": request.Provider,
			"private_latency_ms": request.LatencyMS, "operation_id": request.OperationID})
		if request.Action == "AGENT" {
			state.ReadyCount.Add(1)
		} else if request.Action != "NOOP" {
			go func(req privateRequest, s *resultState) {
				started := time.Now().UnixNano()
				time.Sleep(time.Duration(req.LatencyMS * float64(time.Millisecond)))
				completed := time.Now().UnixNano()
				s.ReadyCount.Add(1)
				if req.Action == "TOOL" {
					s.EffectCount.Add(1)
				}
				private.write(map[string]any{"episode_token": req.EpisodeToken,
					"operation_id": req.OperationID, "private_started_ns": started,
					"private_completed_ns": completed, "private_effect_count": s.EffectCount.Load()})
			}(request, state)
		}
		jobs <- responseJob{Deadline: deadline, Episode: request.EpisodeToken, Slot: request.Slot}
	}
	close(jobs)
	<-done
}

func runClient(address, workloadPath, hostPath string) {
	raw, err := os.ReadFile(workloadPath)
	if err != nil {
		panic(err)
	}
	var work workload
	if err := json.Unmarshal(raw, &work); err != nil {
		panic(err)
	}
	conn, err := net.Dial("tcp", address)
	if err != nil {
		panic(err)
	}
	defer conn.Close()
	if tcp, ok := conn.(*net.TCPConn); ok {
		tcp.SetNoDelay(true)
	}
	hostFile, _ := os.Create(hostPath)
	defer hostFile.Close()
	host := &jsonWriter{w: bufio.NewWriter(hostFile)}

	totalResponses := 0
	for _, ep := range work.Episodes {
		totalResponses += len(ep.Frames)
	}
	responses := make(chan map[string]any, totalResponses)
	go func() {
		for index := 0; index < totalResponses; index++ {
			frame, err := readFrame(conn, work.FrameBytes)
			if err != nil {
				panic(err)
			}
			arrival := time.Now().UnixNano()
			episode := binary.BigEndian.Uint64(frame[0:8])
			slot := int(binary.BigEndian.Uint32(frame[8:12]))
			responses <- map[string]any{"episode_token": episode, "slot": slot,
				"cloud_response_receive_ns": arrival, "response_bytes": len(frame),
				"destination": "CommonActionGateway"}
		}
		close(responses)
	}()

	for _, ep := range work.Episodes {
		start := time.Now().UnixNano() + work.StartDelayNS
		for index, encoded := range ep.Frames {
			slot := index + 1
			deadline := start + int64(slot)*work.DeltaNS
			waitUntil(deadline)
			frame, err := base64.StdEncoding.DecodeString(encoded)
			if err != nil {
				panic(err)
			}
			binary.BigEndian.PutUint64(frame[0:8], uint64(deadline+work.ResponseLagNS))
			sent := time.Now().UnixNano()
			if err := writeFrame(conn, frame); err != nil {
				panic(err)
			}
			host.write(map[string]any{"episode_token": ep.Token, "slot": slot,
				"cloud_request_scheduled_ns": deadline, "cloud_request_send_ns": sent,
				"request_bytes": len(frame), "destination": "CommonActionGateway",
				"public_profile": work.PublicProfile})
		}
		lastResponse := start + int64(len(ep.Frames))*work.DeltaNS + work.ResponseLagNS
		waitUntil(lastResponse + work.InterEpisodeNS)
	}
	for response := range responses {
		host.write(response)
	}
}

func main() {
	mode := flag.String("mode", "", "gateway or client")
	port := flag.Int("port", 0, "gateway listen port")
	address := flag.String("address", "", "gateway address")
	key := flag.String("key", "", "synthetic experiment AES key")
	workloadPath := flag.String("workload", "", "public/encrypted workload JSON")
	hostPath := flag.String("host-log", "host.jsonl", "host-visible log")
	privatePath := flag.String("private-log", "private.jsonl", "trusted private log")
	frameBytes := flag.Int("frame-bytes", 1024, "fixed frame bytes")
	flag.Parse()
	if *mode == "gateway" {
		runGateway(*port, *key, *hostPath, *privatePath, *frameBytes)
		return
	}
	if *mode == "client" {
		runClient(*address, *workloadPath, *hostPath)
		return
	}
	panic("mode must be gateway or client")
}

// The standard library crypto/rand implementation is isolated here so the
// platform-specific source remains simple and gofmt keeps imports deterministic.
func readCryptoRandom(p []byte) (int, error) {
	return io.ReadFull(cryptographicReader{}, p)
}

type cryptographicReader struct{}

func (cryptographicReader) Read(p []byte) (int, error) {
	// os.Open on Windows does not expose /dev/urandom; use time-independent
	// randomness through crypto/rand in rand_windows.go.
	return platformRandom(p)
}

func sortedKeys(values map[uint64]*resultState) []uint64 {
	keys := make([]uint64, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool { return keys[i] < keys[j] })
	return keys
}
