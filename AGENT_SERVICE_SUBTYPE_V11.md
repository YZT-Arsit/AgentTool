# Private Agent-service subtype V11

Allowed encrypted inner values are `DIRECT_AGENT_SERVICE`, `AGENT_AS_TOOL`, and `HANDOFF`. `PrivateAgentServiceEnvelope` includes version, subtype, validated arguments, and bounded continuation data. Relay public evidence is checked against subtype, logical action, operation ID, and capability strings. All use the same `REAL_AGENT_SERVICE` Gateway route class and public endpoint.

The frozen 1024-byte BHTTP request bucket is unchanged. A conservative 400-byte private application-payload admission bound is enforced. A 372-byte near-bound envelope passed at 1079 final OHTTP bytes; a 628-byte envelope was rejected before execution instead of resizing the public profile.
