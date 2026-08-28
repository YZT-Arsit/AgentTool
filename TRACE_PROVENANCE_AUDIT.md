# Stage-8 Trace Provenance Audit

## Evidence level and source selection

Primary evidence is **L1 — SOURCE-FAITHFUL REFERENCE IMPLEMENTATION**. It is not
GAAP code and is not a real deployment. A public-code search on 25 August 2026
did not locate an official/author repository. The [GAAP paper,
arXiv:2604.19657v1](https://arxiv.org/abs/2604.19657) states that the authors
plan to release GAAP; no commit hash or code license can therefore be recorded.
The paper uses arXiv's non-exclusive distribution license. Project code was
written from the documented semantics and remains separately labeled.

## Operation provenance

| Operation | Source paper/code | Exact reason | Source-supported? | Project-added? |
|---|---|---|---|---|
| Private-data lookup | GAAP §§3.3.2, 4.2 | Private values are retrieved by key from the private-data DB and tainted with that key | yes | localhost deployment and synthetic record |
| Permission lookup | GAAP §§3.1.1, 3.3.3, 4.3 | External disclosure is checked against a stored data-item/party permission | yes | separate observable service |
| Disclosure-history/provenance lookup | GAAP §§3.3.4, 4.5 | Persistent disclosure state restores indirect/transitive taints across calls/tasks | yes | separate observable service |
| Disclosure-history append | GAAP §§3.3.4, 4.5 | Disclosures are persisted for later flow tracking | yes | synthetic event representation |
| Taint/handle restoration | GAAP §§3.3.1–3.3.4 | IFC tracks private-store keys and representations of API-call sources | yes, semantic | compact local taint descriptor |
| Authorization check | GAAP §§3.1.1, 4.3 | Runtime allows/denies intercepted calls from current policy | yes | deterministic Boolean evaluator |
| Missing-policy prompt | GAAP §3.1.1 steps 4–5 | Inconclusive disclosure pauses execution and asks the user | yes | local synthetic consent service |
| Permission persistence | GAAP §3.1.1 step 5 | User decision is saved to avoid future prompts | yes | synthetic policy record |
| Tool argument construction | GAAP code-artifact/MCP model, §§3.1, 3.3.1 | Trusted execution constructs an intercepted external call from tainted data | partially | minimal typed synthetic action |
| Effect execution | GAAP §§3.1, 3.3.1, 4.4 | Agent invokes external MCP tools and GAAP intercepts the call | yes | local idempotent-effect abstraction |
| Multi-shot retry/replan | GAAP multi-shot support, §§2–3 and 4.1 | Execution may pause, call the model again, and continue | yes, semantic | deterministic planner instead of LLM |
| Per-service ORAM | prior-art baseline | Hides logical address within each naturally distinct state service | no | yes; known technique |
| Unified oblivious state | prior-art baseline | Places relevant state in one oblivious address space | no | yes; known technique |
| Fixed canonical slots | prior-art baseline | Executes maximum schema slots every action | no | yes; known technique |
| Trusted-local state | design baseline | Keeps selected state inside the trusted mediator | no | yes; Stage-6-consistent baseline |

The decisive runtime condition is
`state.taint_origin == "direct_private_db"`: it selects the source-supported
private-data lookup; otherwise the runtime restores persistent transitive
provenance from the disclosure log. `requires_history` is derived later from
that already-generated state. It is never supplied to the mediator.

## Host-observation provenance

| Visible field | Why the host can observe it |
|---|---|
| timestamp/duration | host schedules processes and terminates TCP connections |
| source process | host operates the mediation/runtime environment |
| destination service | modular services use distinct processes/ports |
| operation class | direct service method or generic `ORAM_ACCESS` crosses the boundary |
| request/response bytes | host transports serialized frames |
| ordered request count | host observes connection sequence and episode boundary |
| stable address token | direct encrypted storage still exposes a physical/stable address |
| ORAM path identifier | the storage host serves the selected physical path |
| action index/type | action class, action count, and coarse episode boundary are allowed leakage |

No host trace contains logical IDs, taint origins, policy values, consent values,
plaintext, labels, or real/dummy markers. The raw event file and private ground
truth are separate. Tests inspect both fields and source code.

## Generation invariant

The executable order is: generate enterprise state; generate task independently;
execute planner/mediator; capture trace; derive evaluation labels. The
`generation_order_audit.csv` and tests enforce this ordering. There is no
`hidden_class`/`private_label` branch in the mediator.

