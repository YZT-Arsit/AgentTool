# Stage-6 Consistency Model

## Permission freshness

Permission reads/validations are linearizable within the authoritative
Permission or Unified service. An action's authorization linearization point is
its authoritative permission read. If an administrator's revocation completes
before an action starts, every architecture must deny that action. If a revoke
races after the action's permission read, the action may complete under the
earlier version; Stage 6 does not implement a cross-service transaction spanning
policy read and external effect.

Hybrid caches never authorize without a remote validation on that action. There
is no lease. Consequently:

- stale window between completed actions: zero;
- revocation delay after acknowledged update: zero subsequent actions;
- DENY→ALLOW visibility: the next validation;
- extra Hybrid freshness cost: one request/response per action.

## Private-data reads

Private data has read-current semantics at the service request. The experiment
does not modify private data concurrently, version document content, or provide
a snapshot transaction across private and permission services.

## Disclosure-log consistency

Each authoritative log serializes operations under a service lock. Appends are
linearizable, ordered, and idempotent by `(tenant, request_id)`. Concurrent
append handlers cannot lose updates. A read or sync beginning after an append
acknowledgment observes that append.

HYBRID-PH caches are per tenant/device. Before every action the mediator sends
the cached version and receives all later events in order. Its consultation
linearizes at this sync. The subsequent append is authoritative first and then
advances that device's local version.

## Multi-device visibility

If device A's append completes before device B begins its sync/read, device B
must observe A's event. The automated two-device experiment checks this for all
protected architectures. HYBRID-PH cannot safely use a purely local log because
another device and the administrator/global audit system can advance the
authoritative version.

## Authorization and effect ordering

The order is permission decision → idempotent tool effect → authoritative log
append. Denied requests never call the tool or append a disclosure. There is no
atomic transaction between the external tool and the log.

## Failure and retry behavior

Tool effects and log appends independently retain request IDs. Retrying the same
action does not duplicate the mock SEND effect or log entry. A crash after the
tool but before log append can be repaired by retrying the same request ID: the
tool reports a duplicate and the append completes idempotently.

This is not a durable PREVIEW/COMMIT protocol. The prototype does not model
process crash persistence, distributed consensus, exactly-once delivery across
machine loss, or durable recovery of a mediator's local Hybrid cache.

## Equivalent-security gate

Primary performance ranking requires privacy sanity, authorization equivalence,
next-action revocation, DENY→ALLOW visibility, authoritative ordered history,
two-device visibility, concurrency correctness, and idempotent effects. Direct
and independent modular traces fail privacy and are retained only as references.

