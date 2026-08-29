# Public Profile Invariants V7

`PUBLIC_PROFILE_V7.json` freezes the future canonical local profile at 128
rounds, 2,048-byte request and response OHTTP bodies, 50 ms period, 25 ms
response lag, at most 100 admitted operations, 6.4 s public lifetime, and
persistent local Relay/Gateway connections.

The loopback Relay integration test independently exercised two 1,024-byte
opaque request/response exchanges. It proved exact request forwarding, exact
response forwarding, equal configured lengths, rejection of a 17-byte request
before Gateway invocation, stable local endpoints, and Relay-to-Gateway
connection reuse. Public log records contain profile/round/length/endpoint/
connection/timestamps; private operation/action/emulator/status fields are a
separate type and are absent from serialized public records.

Because the fixture bytes are not RFC 9458 Encapsulated Messages, the canonical
public request size, response size, and round-count statuses remain
`NOT_TESTED`. No traffic-analysis or packet-timing conclusion follows from the
Relay test.

