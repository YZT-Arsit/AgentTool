//go:build ignore

// V10A freeze-time ABI check. It serializes every selected operation ID through
// the accepted RFC 9292 codec without executing an Agent, Tool, or holdout case.
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"common-action-gateway-v2/v7ohttp"
	"common-action-gateway-v2/v9ohttp"
)

type input struct { OperationIDs []string `json:"operation_ids"` }

func main() {
	if len(os.Args) != 2 { panic("usage: operation_id_abi_check IDs.json") }
	b, err := os.ReadFile(os.Args[1]); if err != nil { panic(err) }
	var in input; if err := json.Unmarshal(b, &in); err != nil { panic(err) }
	codec := v9ohttp.RFC9292Codec{}
	seen := map[string]bool{}
	for _, id := range in.OperationIDs {
		if id == "" || len([]byte(id)) > 32 || seen[id] { panic("invalid or duplicate operation ID") }
		seen[id] = true
		plain, err := codec.EncodeKnownLengthRequest(v7ohttp.InnerSemanticTarget, v7ohttp.PrivateActionMessage{
			ProtocolVersion: 1, Kind: v7ohttp.ActionRealTool, RouteHandle: []byte("route-tool-read"),
			OperationID: []byte(id), ProtectedArgs: []byte("v10-freeze-abi-only"), Authorization: []byte("local-test"),
		}, 1024)
		if err != nil { panic(err) }
		_, decoded, err := codec.DecodeKnownLengthRequest(plain); if err != nil { panic(err) }
		if string(decoded.OperationID) != id { panic("operation ID truncated or changed") }
	}
	fmt.Printf("PASS operation_ids=%d canonical_bhttp_bytes=1024\n", len(in.OperationIDs))
}
