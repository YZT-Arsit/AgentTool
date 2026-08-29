# Trusted Module TCB V7-OHTTP

## Current code inventory

At this snapshot, `action_privacy_v7_ohttp` contains 218 physical lines across
four Python files (including exports and comments). It implements only semantic
models, authorization-preserving route resolution, key/transport contracts,
and fail-closed status. The offline framework classifier/compiler, corpus
tooling, experiment scripts, and native OpenAI/Microsoft runtimes are not in
this runtime TCB.

The intended future trusted module also contains the official SimplePIR client
and recovery code, descriptor authentication, an RFC 9458 OHTTP client, its RFC
9292 codec, key configuration, and per-slot response contexts. Third-party
cryptographic code must be counted separately from our application code.

## Third-party status

- Official SimplePIR: integrated and separately pinned at commit
  `e9020b03bf2872c75b8954e749e32408b5db87ed`.
- RFC 9458/RFC 9292 library: 0 integrated lines; dependency absent offline.
- Legacy AES-GCM ActionCell/Envelope codec: excluded from canonical V7-OHTTP
  TCB and retained only for historical evidence.

## Trusted state and interfaces

Trusted state includes descriptor keys/state, AgentDescriptor plaintext,
ActionRouteMap, Gateway authenticated public key configuration, private action
intent, operation/session state, and OHTTP request contexts. The public
interface emits only fixed-profile encapsulated bytes and receives encapsulated
responses.

Hardware TEE attestation remains `NOT_TESTED`.
