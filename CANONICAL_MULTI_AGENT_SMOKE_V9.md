
# Canonical Multi-Agent Smoke V9

Result: **4/4 PASS**.

- `agent-a`: provider calls 1, delivered 1, PASS=True
- `agent-b`: provider calls 1, delivered 1, PASS=True
- `agent-c`: provider calls 1, delivered 1, PASS=True
- `agent-a-forbidden-b`: provider calls 0, delivered 0, PASS=True

The three positive cases used distinct real SimplePIR-selected descriptors. The negative A-to-B capability attempt failed in `TrustedActionRouter` before any provider invocation.
