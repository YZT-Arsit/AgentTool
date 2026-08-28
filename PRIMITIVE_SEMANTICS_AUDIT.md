# Primitive Semantics Audit — historical boundary record

The active design rejects ORAM and visible cover sets as Agent/Tool invocation
privacy mechanisms. Retained ORAM code is optional private-state storage only.

## Decision

The advisor hypothesis combines three distinct privacy problems. They require different mechanisms:

| Secret | Observer | Appropriate primitive | What it does not hide |
|---|---|---|---|
| Registry logical address | Registry/storage host | ORAM, or PIR for read-only retrieval | A subsequent direct network destination |
| Read query/index | Database server | PIR; SPIR also limits what the client learns | The index from the querying client |
| Prompt and routing computation | Routing provider | MPC/2PC, FHE, a TEE, or a local trusted router | Network endpoint metadata after plaintext dispatch |
| Selected remote endpoint | Infrastructure observer | Full cover, an anonymity/private-relay layer, or a shared dispatcher/mailbox | The selected provider from itself after it decrypts real work |
| Adaptive approval/retry path | Mediation host | Bounded schedule normalization plus protected state access | Channels omitted from the schedule, such as unshaped timing |

ORAM-backed state, PIR-backed registry retrieval, and private dispatch may coexist, but they are not interchangeable.

## 1. ORAM

Standard ORAM hides the sequence of logical memory addresses from the storage server, up to declared public leakage such as database size and the number of accesses. It does not cause every logical record, specialist agent, or remote endpoint to execute.

For Path ORAM, one logical read/write fetches and rewrites a root-to-leaf path. With a binary tree containing `N` logical blocks, fixed bucket capacity `Z`, and block size `B`, a non-recursive logical access touches `Theta(log N)` buckets and transfers `Theta(Z B log N)` bytes. The client also needs a position map; stored directly, it is `Theta(N log N)` bits, while recursive ORAM reduces trusted position-map storage at the cost of additional recursive accesses. The stash is trusted client state, not an all-record scan.

Therefore:

```text
ORAM memory access != all-agent cover execution
```

Calling an `O(N)` set of agent invocations an “ORAM access” is incorrect. The project continues to use Path ORAM only for logical private-state/registry accesses. It makes no new ORAM claim. The underlying semantics follow the [Path ORAM paper](https://arxiv.org/abs/1202.5150).

## 2. PIR, SPIR, and OT

The standard PIR roles are:

```text
client: holds index i and constructs the query
server: holds database DB and processes the query
client: learns DB[i]
server: should not learn i
```

PIR schemes have different cost profiles. A single-server computational PIR can reduce communication below downloading the database, but ordinary constructions may still require linear or near-linear server work unless they use preprocessing or additional assumptions. Stage 11 therefore does not assign one universal PIR asymptotic cost; any experiment must name its concrete scheme.

PIR does not generally protect the database from a malicious client. SPIR adds server/database privacy so the client learns only the authorized item. One-out-of-`N` oblivious transfer similarly lets a receiver choose one item without revealing the choice to the sender while limiting the receiver to that item; it still assumes the receiver knows its choice.

The claim below is false under standard PIR:

> “PIR lets an LLM choose agent `i` while the same LLM does not know `i`.”

If the LLM is the PIR client and chooses `i`, it necessarily possesses or computes `i`. A coherent placement is:

```text
decision LLM -> opaque semantic capability h
trusted/private resolver: h -> concrete index i
resolver -> PIR/SPIR/OT query -> untrusted registry
```

This hides `i` from the registry, not from the resolver. It also does not hide a later direct call to endpoint `i` from a network/infrastructure observer.

## 3. Private routing computation

PIR retrieves a selected database entry; it does not privately evaluate an arbitrary prompt-dependent routing model. If a routing provider must not see the prompt, the routing function needs one of:

- a local trusted router/private resolver;
- a TEE with an explicit hardware and side-channel trust boundary;
- 2PC/MPC between suitable non-colluding parties;
- FHE/private inference with an explicit key and output-recipient model.

[PPRoute](https://arxiv.org/abs/2604.15728) places encoder inference and nearest-neighbor routing under MPC and directly addresses private query computation. Standard PIR is not a substitute for that design. [CryptoMoE](https://arxiv.org/abs/2511.01197) protects secret-shared token-to-expert routing and uses balanced expert loads and secure dispatch/combine inside MoE inference. Those systems materially limit any novelty claim for private routing itself.

## 4. All-agent cover execution

Full-cover dispatch sends a fixed-size slot to every candidate endpoint on the same public cadence. Exactly one encrypted envelope contains authorized real work; the others must terminate as authenticated internal no-ops before any external effect. Under non-colluding endpoint and infrastructure observers, this can hide the selected endpoint from infrastructure if real and cover envelopes are indistinguishable there.

Its direct cost is `Theta(N)` endpoint messages and, if each endpoint must process its envelope indistinguishably, `Theta(N)` agent-side envelope processing. It is a cover-traffic baseline, not ORAM.

It cannot hide selection from the selected specialist provider after decryption. It also fails under collusion between the infrastructure observer and that provider, unless a stronger secure-computation architecture changes what the provider learns.

## 5. Endpoint-privacy feasibility boundary

The following six goals cannot all be obtained by ORAM/PIR alone:

1. useful routing;
2. hidden concrete agent identity;
3. no dummy external effects;
4. sub-`O(N)` agent execution cost;
5. no trusted global dispatcher/relay;
6. direct calls to distinct observable remote endpoints.

With direct distinct endpoints, the destination is the selected-agent identifier for an infrastructure observer. Eliminating `O(N)` cover requires some shared indirection, anonymity system, non-colluding relay arrangement, or secure dispatcher. Such a component changes the trust/deployment story. Bucketed or hierarchical cover can lower cost but leaks the selected bucket and therefore does not preserve the full-cover leakage class.

## 6. Stage-11 gate

```text
Does ORAM mean all-agent invocation?: NO
Can standard PIR hide the chosen index from its own client?: NO
Can ORAM/PIR alone hide a direct distinct endpoint?: NO
Should a new ORAM primitive be developed?: NO
```

The actual bottlenecks are cover-dispatch fanout and fixed-cadence waiting, not Path ORAM bandwidth in the proposed configuration. Stage 11 will not invent a new ORAM construction.
