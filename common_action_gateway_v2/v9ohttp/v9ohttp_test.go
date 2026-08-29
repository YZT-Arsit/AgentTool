package v9ohttp

import (
	"bytes"
	"testing"

	"common-action-gateway-v2/v7ohttp"
	ohttp "github.com/chris-wood/ohttp-go"
)

func testBackends(t *testing.T) (*RFC9458Client, *RFC9458Gateway, PublicSuite, ohttp.PrivateConfig) {
	t.Helper()
	private, err := ohttp.NewConfig(
		7, 0x0020, 0x0001, 0x0001,
	)
	if err != nil {
		t.Fatal(err)
	}
	suite := PublicSuite{
		KeyID: 7, KEMID: 0x0020,
		KDFID: 0x0001, AEADID: 0x0001,
		ConfigurationEpoch: 3, AuthenticatedSource: "V9_TEST_FIXTURE",
	}
	client, err := NewRFC9458Client(private.Config(), suite)
	if err != nil {
		t.Fatal(err)
	}
	gateway, err := NewRFC9458Gateway(private, suite)
	if err != nil {
		t.Fatal(err)
	}
	return client, gateway, suite, private
}

func action(kind v7ohttp.ActionKind) v7ohttp.PrivateActionMessage {
	message := v7ohttp.PrivateActionMessage{
		ProtocolVersion: 1, Kind: kind, OperationID: []byte("op-1"),
	}
	if kind != v7ohttp.ActionNoop {
		message.RouteHandle = []byte("private-route")
		message.ProtectedArgs = []byte("protected-arguments")
		message.Authorization = []byte("private-policy-token")
	}
	return message
}

func TestRFC9292AllActionCasesRoundTripWithCanonicalPadding(t *testing.T) {
	codec := RFC9292Codec{}
	for _, kind := range []v7ohttp.ActionKind{
		v7ohttp.ActionNoop, v7ohttp.ActionRealTool,
		v7ohttp.ActionAgentService, v7ohttp.ActionExternalHTTP,
	} {
		encoded, err := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, action(kind), 1024)
		if err != nil {
			t.Fatalf("%s encode: %v", kind, err)
		}
		if len(encoded) != 1024 {
			t.Fatalf("%s length=%d", kind, len(encoded))
		}
		target, decoded, err := codec.DecodeKnownLengthRequest(encoded)
		if err != nil {
			t.Fatalf("%s decode: %v", kind, err)
		}
		if target != v7ohttp.InnerSemanticTarget || decoded.Kind != kind ||
			!bytes.Equal(decoded.OperationID, []byte("op-1")) {
			t.Fatalf("%s semantic mismatch", kind)
		}
	}
}

func TestRFC9292AllResponseCasesRoundTrip(t *testing.T) {
	codec := RFC9292Codec{}
	for _, status := range []byte{
		StatusWait, StatusResult, StatusError, StatusTimeout,
		StatusEffectOutcomeUnknown, StatusProfileOverflow,
	} {
		input := v7ohttp.PrivateResponse{Status: status, OperationID: "op", Payload: []byte("protected")}
		encoded, err := codec.EncodeKnownLengthResponse(input, 768)
		if err != nil {
			t.Fatal(err)
		}
		decoded, err := codec.DecodeKnownLengthResponse(encoded)
		if err != nil {
			t.Fatal(err)
		}
		if decoded.Status != input.Status || decoded.OperationID != input.OperationID ||
			!bytes.Equal(decoded.Payload, input.Payload) {
			t.Fatal("response semantic mismatch")
		}
	}
}

func TestRFC9292RejectsMalformedAndNonzeroPadding(t *testing.T) {
	codec := RFC9292Codec{}
	encoded, err := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, action(v7ohttp.ActionRealTool), 512)
	if err != nil {
		t.Fatal(err)
	}
	encoded[len(encoded)-1] = 1
	if _, _, err := codec.DecodeKnownLengthRequest(encoded); err == nil {
		t.Fatal("non-zero padding accepted")
	}
	encoded[0] = 2
	if _, _, err := codec.DecodeKnownLengthRequest(encoded); err == nil {
		t.Fatal("unknown-length request accepted")
	}
}

func TestRFC9458PerSlotRoundTripAndContextBinding(t *testing.T) {
	client, gateway, _, _ := testBackends(t)
	slot := v7ohttp.SlotID{Session: 1, Slot: 4}
	requestPlain := bytes.Repeat([]byte{0x41}, 1024)
	requestWire, clientContext, err := client.EncapsulateRequest(slot, requestPlain)
	if err != nil {
		t.Fatal(err)
	}
	opened, serverContext, err := gateway.DecapsulateRequest(slot, requestWire)
	if err != nil || !bytes.Equal(opened, requestPlain) {
		t.Fatalf("request round trip: %v", err)
	}
	responsePlain := bytes.Repeat([]byte{0x42}, 768)
	responseWire, err := gateway.EncapsulateResponse(serverContext, responsePlain)
	if err != nil {
		t.Fatal(err)
	}
	responseOpened, err := client.DecapsulateResponse(clientContext, responseWire)
	if err != nil || !bytes.Equal(responseOpened, responsePlain) {
		t.Fatalf("response round trip: %v", err)
	}
	if _, err := client.DecapsulateResponse(clientContext, responseWire); err == nil {
		t.Fatal("client context reuse accepted")
	}
	if _, err := gateway.EncapsulateResponse(serverContext, responsePlain); err == nil {
		t.Fatal("server context reuse accepted")
	}
}

func TestRFC9458WrongSlotAndModifiedResponseFail(t *testing.T) {
	client, gateway, _, _ := testBackends(t)
	request := bytes.Repeat([]byte{0x33}, 512)
	wireA, clientA, _ := client.EncapsulateRequest(v7ohttp.SlotID{Session: 1, Slot: 1}, request)
	_, serverA, _ := gateway.DecapsulateRequest(v7ohttp.SlotID{Session: 1, Slot: 1}, wireA)
	wireB, clientB, _ := client.EncapsulateRequest(v7ohttp.SlotID{Session: 1, Slot: 2}, request)
	_, serverB, _ := gateway.DecapsulateRequest(v7ohttp.SlotID{Session: 1, Slot: 2}, wireB)
	responseA, _ := gateway.EncapsulateResponse(serverA, []byte("result-A"))
	responseB, _ := gateway.EncapsulateResponse(serverB, []byte("result-B"))
	if _, err := client.DecapsulateResponse(clientA, responseB); err == nil {
		t.Fatal("wrong-slot response context accepted")
	}
	responseB[len(responseB)-1] ^= 1
	if _, err := client.DecapsulateResponse(clientB, responseB); err == nil {
		t.Fatal("modified response accepted")
	}
	_ = responseA
}

func TestRFC9458RejectsTruncatedAndUnconfiguredSuite(t *testing.T) {
	client, gateway, _, _ := testBackends(t)
	wire, context, err := client.EncapsulateRequest(v7ohttp.SlotID{Session: 1, Slot: 1}, []byte("request"))
	if err != nil {
		t.Fatal(err)
	}
	tampered := append([]byte(nil), wire...)
	tampered[4] ^= 1
	if _, _, err := gateway.DecapsulateRequest(v7ohttp.SlotID{Session: 1, Slot: 1}, tampered); err == nil {
		t.Fatal("unconfigured KDF accepted")
	}
	if _, err := client.DecapsulateResponse(context, []byte{1, 2, 3}); err == nil {
		t.Fatal("truncated response accepted")
	}
}

func TestActualOHTTPLengthsEqualWithinPublicBHTTPBuckets(t *testing.T) {
	client, gateway, _, _ := testBackends(t)
	codec := RFC9292Codec{}
	var requestLength int
	for index, kind := range []v7ohttp.ActionKind{
		v7ohttp.ActionNoop, v7ohttp.ActionRealTool,
		v7ohttp.ActionAgentService, v7ohttp.ActionExternalHTTP,
	} {
		plain, err := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, action(kind), 1024)
		if err != nil {
			t.Fatal(err)
		}
		wire, _, err := client.EncapsulateRequest(v7ohttp.SlotID{Session: 1, Slot: uint32(index + 1)}, plain)
		if err != nil {
			t.Fatal(err)
		}
		if index == 0 {
			requestLength = len(wire)
		} else if len(wire) != requestLength {
			t.Fatalf("request size differs: %d vs %d", len(wire), requestLength)
		}
	}

	var responseLength int
	for index, status := range []byte{StatusWait, StatusResult, StatusError, StatusTimeout, StatusEffectOutcomeUnknown} {
		requestWire, _, _ := client.EncapsulateRequest(v7ohttp.SlotID{Session: 2, Slot: uint32(index + 1)}, bytes.Repeat([]byte{0}, 1024))
		_, serverContext, err := gateway.DecapsulateRequest(v7ohttp.SlotID{Session: 2, Slot: uint32(index + 1)}, requestWire)
		if err != nil {
			t.Fatal(err)
		}
		plain, err := codec.EncodeKnownLengthResponse(v7ohttp.PrivateResponse{Status: status, OperationID: "op", Payload: []byte("protected")}, 768)
		if err != nil {
			t.Fatal(err)
		}
		wire, err := gateway.EncapsulateResponse(serverContext, plain)
		if err != nil {
			t.Fatal(err)
		}
		if index == 0 {
			responseLength = len(wire)
		} else if len(wire) != responseLength {
			t.Fatalf("response size differs: %d vs %d", len(wire), responseLength)
		}
	}
}

func TestPublicConfigMultipleSuitesRoundTrip(t *testing.T) {
	_, _, _, private := testBackends(t)
	config := private.Config()
	config.Suites = append(config.Suites, ohttp.ConfigCipherSuite{
		KDFID: 0x0002, AEADID: 0x0003,
	})
	decoded, err := ohttp.UnmarshalPublicConfig(config.Marshal())
	if err != nil {
		t.Fatal(err)
	}
	if !config.IsEqual(decoded) || len(decoded.Suites) != 2 {
		t.Fatal("multiple-suite Gateway configuration changed")
	}
}

func TestReportActualRFCExpansion(t *testing.T) {
	client, gateway, _, _ := testBackends(t)
	codec := RFC9292Codec{}
	for index, kind := range []v7ohttp.ActionKind{
		v7ohttp.ActionNoop, v7ohttp.ActionRealTool,
		v7ohttp.ActionAgentService, v7ohttp.ActionExternalHTTP,
	} {
		minimum := 0
		for size := 1; size <= 1024; size++ {
			if _, err := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, action(kind), size); err == nil {
				minimum = size
				break
			}
		}
		plain, _ := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, action(kind), 1024)
		wire, _, err := client.EncapsulateRequest(v7ohttp.SlotID{Session: 20, Slot: uint32(index + 1)}, plain)
		if err != nil || minimum == 0 {
			t.Fatalf("request expansion %s: minimum=%d err=%v", kind, minimum, err)
		}
		t.Logf("request kind=%s canonical_bhttp=%d padded_bhttp=%d final_ohttp=%d", kind, minimum, len(plain), len(wire))
	}
	for index, status := range []byte{StatusWait, StatusResult, StatusError, StatusTimeout, StatusEffectOutcomeUnknown} {
		value := v7ohttp.PrivateResponse{Status: status, OperationID: "op", Payload: []byte("protected")}
		minimum := 0
		for size := 1; size <= 768; size++ {
			if _, err := codec.EncodeKnownLengthResponse(value, size); err == nil {
				minimum = size
				break
			}
		}
		requestWire, _, _ := client.EncapsulateRequest(v7ohttp.SlotID{Session: 21, Slot: uint32(index + 1)}, bytes.Repeat([]byte{0}, 1024))
		_, context, err := gateway.DecapsulateRequest(v7ohttp.SlotID{Session: 21, Slot: uint32(index + 1)}, requestWire)
		if err != nil {
			t.Fatal(err)
		}
		plain, _ := codec.EncodeKnownLengthResponse(value, 768)
		wire, err := gateway.EncapsulateResponse(context, plain)
		if err != nil || minimum == 0 {
			t.Fatalf("response expansion %d: minimum=%d err=%v", status, minimum, err)
		}
		t.Logf("response status=%d canonical_bhttp=%d padded_bhttp=%d final_ohttp=%d", status, minimum, len(plain), len(wire))
	}
}
