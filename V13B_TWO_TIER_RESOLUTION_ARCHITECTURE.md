# V13B two-tier private Agent-resolution architecture

This engineering specification is intended for later architecture review. It
does not modify the paper.

```text
Employee task
    -> Planner
    -> TEE / Protected Runtime
       |-- one fixed receiver-only PSI slot
       |      <-> Enterprise Agent Directory
       |-- one fixed scheduled PIR slot
       |      <-> Global Agent Library
       -> private resolved Agent target
       -> existing Trusted Gateway ingress
       -> enterprise-deployed Agent
          OR global-library Agent
          OR remote LLM
          OR external Tool/API
          OR local application
```

The PSI slot hides the enterprise availability query subject to a future
receiver-only PSI implementation. The existing PIR slot hides the global
library row. Executing both fixed slots for every opportunity makes the
enterprise-hit and library-fallback public structures identical. The Gateway
is the common observer-visible execution boundary; target source and route are
trusted state after that boundary.

The logically separate Agent-resolution profile does not alter the existing
Gateway/Registry timing profile: H=4500 ms, B=200 ms, Delta=10 ms, M=50,
R=521, Q=100, rho=30 ms, and response preparation lead=20 ms.
