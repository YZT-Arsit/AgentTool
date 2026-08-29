
# Canonical Runner V9

Status: **FUNCTIONAL DEVELOPMENT PASS**. This is not a privacy result and no holdout was created.

The sole entry point is `python -m canonical_v9.runner`. It orchestrates a trusted Python selection/routing client and the pinned Go RFC 9292/RFC 9458 Gateway runner. Every session performs an official SimplePIR query and authenticates the recovered `AgentDescriptorV7`; the descriptor is never substituted after lookup.

The executable path is: real SimplePIR -> descriptor authentication -> `TrustedActionRouter` -> RFC 9292 -> RFC 9458 -> loopback V8 Relay -> RFC 9458 Gateway -> RFC 9292 -> opaque route-table lookup -> asynchronous local provider -> live V7 effect journal -> durable ready queue -> bounded V8 in-memory publication -> `PreparedSlot` -> current-slot OHTTP response -> client decode -> durable `DeliveryLedger` -> framework sink.

Trust statement: process separation on this Linux development host is **not** hardware TEE isolation. `HARDWARE_TEE = NOT_TESTED`.

The first attempted run failed before Gateway execution because Python bytes were not base64-encoded for Go JSON. A later otherwise-successful run was rejected after audit because public profile IDs encoded selected-Agent labels. Both directories are preserved under `results_v9/` and are not cited as passing evidence.
