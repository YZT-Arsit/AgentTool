# V11.1 public preconnection

The canonical runner starts the Gateway and Relay, performs the same public
`GET /preconnect` for every workload, verifies HTTP/2 on both hops, and only
then records `PUBLIC_SETUP_COMPLETE`.  It subsequently prepares the immutable
private slot table and assigns `T0`.

The evidence order is:

1. `GATEWAY_INSTANTIATED`
2. `GATEWAY_READY`
3. `RELAY_READY`
4. `CLIENT_RELAY_HTTP2_ESTABLISHED`
5. `RELAY_GATEWAY_HTTP2_ESTABLISHED`
6. `PUBLIC_SETUP_COMPLETE`
7. `PREPARED_REQUEST_TABLE_COMPLETE`
8. `T0_ASSIGNED`

No provider invocation occurs in preconnect.  The higher-level trusted caller
constructs the encrypted/PIR-selected private plan before process invocation;
the Go runner first inspects that plan's action material only after
`PUBLIC_SETUP_COMPLETE`.  This boundary is stated explicitly rather than
claiming that the surrounding trusted caller did no pre-session work.
