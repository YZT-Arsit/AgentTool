package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"math/big"
	"os"
	"runtime"
	"strconv"
	"time"

	sp "github.com/ahenzinger/simplepir/pir"
)

const (
	recordBytes = uint64(1024)
	recordBits  = recordBytes * 8
	secParam    = uint64(1 << 10)
	logQ        = uint64(32)
)

type request struct {
	Episode string
	Round   int
	Index   uint64
	Class   string
}

type clientTrace struct {
	Episode           string  `json:"episode"`
	Round             int     `json:"round"`
	Index             uint64  `json:"private_index"`
	Class             string  `json:"private_class"`
	QueryGenerationMs float64 `json:"query_generation_ms"`
	RecoveryMs        float64 `json:"recovery_ms"`
	Correct           bool    `json:"correct"`
}

type serverTrace struct {
	Ordinal     int     `json:"ordinal"`
	QueryBytes  uint64  `json:"query_bytes"`
	QueryRows   uint64  `json:"query_rows"`
	QueryCols   uint64  `json:"query_cols"`
	QuerySHA256 string  `json:"query_sha256"`
	AnswerBytes uint64  `json:"answer_bytes"`
	AnswerMs    float64 `json:"answer_ms"`
	Executor    string  `json:"executor"`
	RequestKind string  `json:"request_kind"`
	ScheduledNs int64   `json:"scheduled_ns,omitempty"`
	ArrivalNs   int64   `json:"request_arrival_ns,omitempty"`
	ReadyNs     int64   `json:"answer_ready_ns,omitempty"`
}

type recoveredTrace struct {
	Episode string `json:"episode"`
	Round   int    `json:"round"`
	Record  string `json:"record_base64"`
}

type interactiveRequest struct {
	OperationID string `json:"operation_id"`
	Index       uint64 `json:"index"`
}

type interactiveResponse struct {
	Type        string `json:"type"`
	OperationID string `json:"operation_id,omitempty"`
	Record      string `json:"record_base64,omitempty"`
	QuerySHA256 string `json:"query_sha256,omitempty"`
	QueryBytes  uint64 `json:"query_bytes,omitempty"`
	AnswerBytes uint64 `json:"answer_bytes,omitempty"`
	Correct     bool   `json:"correct,omitempty"`
	Error       string `json:"error,omitempty"`
}

type metrics struct {
	Backend                    string  `json:"backend"`
	Commit                     string  `json:"commit"`
	LogicalRecords             uint64  `json:"logical_records"`
	PhysicalRecordCapacity     uint64  `json:"physical_record_capacity"`
	LogicalBytes               uint64  `json:"logical_bytes"`
	PhysicalBytes              uint64  `json:"physical_bytes"`
	PaddingBytes               uint64  `json:"padding_bytes"`
	Rows                       uint64  `json:"matrix_rows"`
	Columns                    uint64  `json:"matrix_columns"`
	PlaintextModulus           uint64  `json:"plaintext_modulus"`
	ElementsPerRecord          uint64  `json:"elements_per_record"`
	DatabaseReadMs             float64 `json:"database_read_ms"`
	DatabaseConstructionMs     float64 `json:"database_construction_ms"`
	SharedStateGenerationMs    float64 `json:"shared_state_generation_ms"`
	FullPreprocessingSetupMs   float64 `json:"full_preprocessing_setup_ms"`
	HintBytes                  uint64  `json:"hint_bytes"`
	PersistentClientStateBytes uint64  `json:"persistent_client_state_bytes"`
	MeanQueryGenerationMs      float64 `json:"mean_query_generation_ms"`
	MeanServerAnswerMs         float64 `json:"mean_server_answer_ms"`
	MeanClientRecoveryMs       float64 `json:"mean_client_recovery_ms"`
	OnlineUploadBytes          uint64  `json:"online_upload_bytes"`
	OnlineDownloadBytes        uint64  `json:"online_download_bytes"`
	Queries                    int     `json:"queries"`
	CorrectQueries             int     `json:"correct_queries"`
	FreshRepeatedQueries       bool    `json:"fresh_repeated_queries"`
	PeakAllocatedBytes         uint64  `json:"peak_allocated_bytes"`
}

func matrixBytes(m *sp.Matrix) []byte {
	out := make([]byte, 16+4*m.Size())
	binary.LittleEndian.PutUint64(out[0:8], m.Rows)
	binary.LittleEndian.PutUint64(out[8:16], m.Cols)
	for i := uint64(0); i < m.Rows; i++ {
		for j := uint64(0); j < m.Cols; j++ {
			binary.LittleEndian.PutUint32(out[16+4*(i*m.Cols+j):], uint32(m.Get(i, j)))
		}
	}
	return out
}

func msgBytes(msg sp.Msg) []byte {
	var out []byte
	for _, matrix := range msg.Data {
		out = append(out, matrixBytes(matrix)...)
	}
	return out
}

func reverseCopy(value []byte) []byte {
	out := make([]byte, len(value))
	for i := range value {
		out[len(value)-1-i] = value[i]
	}
	return out
}

func buildDatabase(path string, count uint64, params *sp.Params) (*sp.Database, []byte, float64, float64) {
	started := time.Now()
	raw, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	if uint64(len(raw)) != count*recordBytes {
		panic("registry byte length mismatch")
	}
	readMs := float64(time.Since(started).Microseconds()) / 1000.0
	started = time.Now()
	db := sp.SetupDB(count, recordBits, params)
	db.Data = sp.MatrixZeros(params.L, params.M)
	modulus := new(big.Int).SetUint64(db.Info.P)
	for i := uint64(0); i < count; i++ {
		record := raw[i*recordBytes : (i+1)*recordBytes]
		value := new(big.Int).SetBytes(reverseCopy(record))
		for digit := uint64(0); digit < db.Info.Ne && value.Sign() != 0; digit++ {
			quotient, remainder := new(big.Int), new(big.Int)
			quotient.QuoRem(value, modulus, remainder)
			db.Data.Set(remainder.Uint64(), (i/params.M)*db.Info.Ne+digit, i%params.M)
			value = quotient
		}
		if value.Sign() != 0 {
			panic("record exceeds declared width")
		}
	}
	db.Data.Sub(db.Info.P / 2)
	return db, raw, readMs, float64(time.Since(started).Microseconds()) / 1000.0
}

func recoverRecord(index uint64, offline sp.Msg, query sp.Msg, answer sp.Msg, shared sp.State,
	client sp.State, params sp.Params, info sp.DBinfo) []byte {
	secret := client.Data[0]
	hint := offline.Data[0]
	ans := answer.Data[0]
	ratio := params.P / 2
	offset := uint64(0)
	for j := uint64(0); j < params.M; j++ {
		offset += ratio * query.Data[0].Get(j, 0)
	}
	offset %= (1 << params.Logq)
	offset = (1 << params.Logq) - offset
	row := index / params.M
	intermediate := sp.MatrixMul(hint, secret)
	ans.MatrixSub(intermediate)
	value := new(big.Int)
	coefficient := big.NewInt(1)
	modulus := new(big.Int).SetUint64(info.P)
	for j := row * info.Ne; j < (row+1)*info.Ne; j++ {
		noised := ans.Get(j, 0) + offset
		denoised := params.Round(noised)
		adjusted := (denoised + info.P/2) % (1 << info.Logq)
		adjusted %= info.P
		term := new(big.Int).Mul(new(big.Int).SetUint64(adjusted), coefficient)
		value.Add(value, term)
		coefficient.Mul(coefficient, modulus)
	}
	ans.MatrixAdd(intermediate)
	encoded := reverseCopy(value.Bytes())
	out := make([]byte, recordBytes)
	copy(out, encoded)
	return out
}

func answerUnpacked(db *sp.Database, query sp.Msg, params sp.Params) sp.Msg {
	// Equivalent SimplePIR server multiplication without the upstream packed
	// AVX-style kernel. The upstream kernel reads rows in groups of eight and
	// faults when the valid 100K parameter height is not a multiple of eight.
	vector := query.Data[0]
	if vector.Rows > params.M {
		vector = vector.SelectRows(0, params.M)
	}
	return sp.MakeMsg(sp.MatrixMulVec(db.Data, vector))
}

func readRequests(path string, recordCount uint64) []request {
	handle, err := os.Open(path)
	if err != nil {
		panic(err)
	}
	defer handle.Close()
	rows, err := csv.NewReader(handle).ReadAll()
	if err != nil {
		panic(err)
	}
	var out []request
	for n, row := range rows {
		if n == 0 {
			continue
		}
		if len(row) != 4 {
			panic("query CSV requires episode,round,index,class")
		}
		round, err := strconv.Atoi(row[1])
		if err != nil {
			panic(err)
		}
		index, err := strconv.ParseUint(row[2], 10, 64)
		if err != nil {
			panic(err)
		}
		if index >= recordCount {
			panic("query index out of range")
		}
		out = append(out, request{row[0], round, index, row[3]})
	}
	return out
}

func createJSONL(path string) (*os.File, *bufio.Writer) {
	file, err := os.Create(path)
	if err != nil {
		panic(err)
	}
	return file, bufio.NewWriter(file)
}

func writeJSON(writer *bufio.Writer, value any) {
	encoded, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	writer.Write(encoded)
	writer.WriteByte('\n')
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
			runtime.Gosched()
		}
	}
}

func runInteractive(pi sp.SimplePIR, db *sp.Database, raw []byte, shared sp.State, hint sp.Msg,
	params sp.Params, recordCount uint64, clientPath, serverPath string) {
	clientFile, clientWriter := createJSONL(clientPath)
	defer clientFile.Close()
	defer clientWriter.Flush()
	serverFile, serverWriter := createJSONL(serverPath)
	defer serverFile.Close()
	defer serverWriter.Flush()

	encoder := json.NewEncoder(os.Stdout)
	_ = encoder.Encode(map[string]any{
		"type": "PIR_READY", "records": recordCount,
		"future_indices_received": 0,
	})
	reader := bufio.NewScanner(os.Stdin)
	// Requests are tiny fixed-schema control messages, but leave enough room for
	// future protocol metadata without permitting unbounded input.
	reader.Buffer(make([]byte, 4096), 64*1024)
	ordinal := 0
	for reader.Scan() {
		var req interactiveRequest
		if err := json.Unmarshal(reader.Bytes(), &req); err != nil || req.OperationID == "" || req.Index >= recordCount {
			_ = encoder.Encode(interactiveResponse{Type: "PIR_ERROR", Error: "invalid interactive PIR request"})
			continue
		}
		started := time.Now()
		clientState, query := pi.Query(req.Index, shared, params, db.Info)
		queryMs := float64(time.Since(started).Microseconds()) / 1000.0
		serializedQuery := msgBytes(query)
		hash := sha256.Sum256(serializedQuery)
		started = time.Now()
		answer := answerUnpacked(db, query, params)
		answerMs := float64(time.Since(started).Microseconds()) / 1000.0
		started = time.Now()
		record := recoverRecord(req.Index, hint, query, answer, shared, clientState, params, db.Info)
		recoveryMs := float64(time.Since(started).Microseconds()) / 1000.0
		expected := raw[req.Index*recordBytes : (req.Index+1)*recordBytes]
		correct := string(record) == string(expected)
		queryHash := hex.EncodeToString(hash[:])
		writeJSON(clientWriter, clientTrace{req.OperationID, ordinal, req.Index, "PRIVATE_AGENT_SELECTION", queryMs, recoveryMs, correct})
		writeJSON(serverWriter, serverTrace{ordinal, uint64(len(serializedQuery)), query.Data[0].Rows,
			query.Data[0].Cols, queryHash, answer.Size() * 4, answerMs,
			"SimplePIRServer", "ONLINE_PIR_QUERY", 0, time.Now().UnixNano(), time.Now().UnixNano()})
		clientWriter.Flush()
		serverWriter.Flush()
		_ = encoder.Encode(interactiveResponse{
			Type: "PIR_RESULT", OperationID: req.OperationID,
			Record: base64.StdEncoding.EncodeToString(record), QuerySHA256: queryHash,
			QueryBytes: uint64(len(serializedQuery)), AnswerBytes: answer.Size() * 4, Correct: correct,
		})
		ordinal++
	}
	if err := reader.Err(); err != nil {
		_ = encoder.Encode(interactiveResponse{Type: "PIR_ERROR", Error: "interactive control channel failed"})
	}
}

func main() {
	database := flag.String("database", "", "fixed 1024-byte row file")
	queryCSV := flag.String("queries", "", "private client query CSV")
	records := flag.Uint64("records", 0, "logical record count")
	metricsPath := flag.String("metrics", "metrics.json", "metrics JSON")
	clientPath := flag.String("client-trace", "client.jsonl", "private client trace")
	serverPath := flag.String("server-trace", "server.jsonl", "server-visible trace")
	recoveredPath := flag.String("recovered", "recovered.jsonl", "private recovered records")
	rawQueryPath := flag.String("raw-queries", "raw_queries.bin", "length-prefixed raw server queries")
	commit := flag.String("commit", "unknown", "pinned upstream commit")
	interactive := flag.Bool("interactive", false, "serve online private indices after query-independent preprocessing")
	pacedDeltaMs := flag.Float64("paced-delta-ms", 0, "public native scheduler cadence; zero disables pacing")
	pacedStartDelayMs := flag.Float64("paced-start-delay-ms", 20, "public episode start lead time")
	flag.Parse()
	if *database == "" || (!*interactive && *queryCSV == "") || *records == 0 {
		panic("missing required arguments")
	}

	pi := sp.SimplePIR{}
	params := pi.PickParams(*records, recordBits, secParam, logQ)
	db, raw, readMs, constructMs := buildDatabase(*database, *records, &params)
	var requests []request
	if !*interactive {
		requests = readRequests(*queryCSV, *records)
	}

	started := time.Now()
	shared := pi.Init(db.Info, params)
	sharedMs := float64(time.Since(started).Microseconds()) / 1000.0
	started = time.Now()
	serverState, hint := pi.Setup(db, shared, params)
	setupMs := float64(time.Since(started).Microseconds()) / 1000.0
	_ = serverState
	// Keep values mapped to [0,p] as expected by Recover's p/2 offset, but
	// expand the packed storage so the portable matrix-vector kernel can run.
	db.Data.Unsquish(db.Info.Basis, db.Info.Squishing, db.Info.Cols)
	if *interactive {
		runInteractive(pi, db, raw, shared, hint, params, *records, *clientPath, *serverPath)
		return
	}

	clientFile, clientWriter := createJSONL(*clientPath)
	defer clientFile.Close()
	defer clientWriter.Flush()
	serverFile, serverWriter := createJSONL(*serverPath)
	defer serverFile.Close()
	defer serverWriter.Flush()
	recoveredFile, recoveredWriter := createJSONL(*recoveredPath)
	defer recoveredFile.Close()
	defer recoveredWriter.Flush()
	rawQueries, err := os.Create(*rawQueryPath)
	if err != nil {
		panic(err)
	}
	defer rawQueries.Close()

	var queryTotal, answerTotal, recoveryTotal float64
	correct := 0
	queryHashes := map[uint64]map[string]bool{}
	var uploadBytes, downloadBytes uint64
	var pacedEpisode string
	var pacedStart int64
	for ordinal, req := range requests {
		started = time.Now()
		clientState, query := pi.Query(req.Index, shared, params, db.Info)
		queryMs := float64(time.Since(started).Microseconds()) / 1000.0
		serializedQuery := msgBytes(query)
		hash := sha256.Sum256(serializedQuery)
		binary.Write(rawQueries, binary.LittleEndian, uint64(len(serializedQuery)))
		rawQueries.Write(serializedQuery)
		var scheduledNs, arrivalNs int64
		if *pacedDeltaMs > 0 {
			if req.Episode != pacedEpisode {
				pacedEpisode = req.Episode
				pacedStart = time.Now().Add(time.Duration(*pacedStartDelayMs * float64(time.Millisecond))).UnixNano()
			}
			scheduledNs = pacedStart + int64(float64(req.Round+1)*(*pacedDeltaMs)*float64(time.Millisecond))
			arrivalNs = waitUntil(scheduledNs)
		}

		started = time.Now()
		answer := answerUnpacked(db, query, params)
		answerMs := float64(time.Since(started).Microseconds()) / 1000.0
		readyNs := time.Now().UnixNano()
		started = time.Now()
		record := recoverRecord(req.Index, hint, query, answer, shared, clientState, params, db.Info)
		recoveryMs := float64(time.Since(started).Microseconds()) / 1000.0
		expected := raw[req.Index*recordBytes : (req.Index+1)*recordBytes]
		isCorrect := string(record) == string(expected)
		if isCorrect {
			correct++
		}
		queryTotal += queryMs
		answerTotal += answerMs
		recoveryTotal += recoveryMs
		answerBytes := answer.Size() * 4
		uploadBytes = uint64(len(serializedQuery))
		downloadBytes = answerBytes
		if queryHashes[req.Index] == nil {
			queryHashes[req.Index] = map[string]bool{}
		}
		queryHashes[req.Index][hex.EncodeToString(hash[:])] = true
		writeJSON(clientWriter, clientTrace{req.Episode, req.Round, req.Index, req.Class, queryMs, recoveryMs, isCorrect})
		writeJSON(serverWriter, serverTrace{ordinal, uint64(len(serializedQuery)), query.Data[0].Rows,
			query.Data[0].Cols, hex.EncodeToString(hash[:]), answerBytes, answerMs,
			"SimplePIRServer", "PIR_QUERY", scheduledNs, arrivalNs, readyNs})
		writeJSON(recoveredWriter, recoveredTrace{req.Episode, req.Round, base64.StdEncoding.EncodeToString(record)})
	}

	fresh := true
	for index, hashes := range queryHashes {
		occurrences := 0
		for _, req := range requests {
			if req.Index == index {
				occurrences++
			}
		}
		if occurrences > 1 && len(hashes) != occurrences {
			fresh = false
		}
	}
	physicalCapacity := (params.L / db.Info.Ne) * params.M
	var memory runtime.MemStats
	runtime.ReadMemStats(&memory)
	result := metrics{
		Backend: "OFFICIAL_SIMPLEPIR_FULL_PREPROCESSING", Commit: *commit,
		LogicalRecords: *records, PhysicalRecordCapacity: physicalCapacity,
		LogicalBytes: *records * recordBytes, PhysicalBytes: physicalCapacity * recordBytes,
		PaddingBytes: (physicalCapacity - *records) * recordBytes,
		Rows:         params.L, Columns: params.M, PlaintextModulus: params.P,
		ElementsPerRecord: db.Info.Ne, DatabaseReadMs: readMs, DatabaseConstructionMs: constructMs,
		SharedStateGenerationMs: sharedMs, FullPreprocessingSetupMs: setupMs,
		HintBytes:                  hint.Size() * 4,
		PersistentClientStateBytes: shared.Data[0].Size()*4 + hint.Size()*4,
		MeanQueryGenerationMs:      queryTotal / float64(len(requests)), MeanServerAnswerMs: answerTotal / float64(len(requests)),
		MeanClientRecoveryMs: recoveryTotal / float64(len(requests)), OnlineUploadBytes: uploadBytes,
		OnlineDownloadBytes: downloadBytes, Queries: len(requests), CorrectQueries: correct,
		FreshRepeatedQueries: fresh, PeakAllocatedBytes: memory.Sys,
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(*metricsPath, encoded, 0644); err != nil {
		panic(err)
	}
	fmt.Printf("ACV_SIMPLEPIR_RESULT records=%d correct=%d/%d setup_ms=%.3f\n", *records, correct, len(requests), setupMs)
}
