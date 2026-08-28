from __future__ import annotations

import hashlib
import hmac
import random
import time
from dataclasses import dataclass
from typing import Any

STORES = ("OBJECT_STORE", "POLICY_STORE", "CREDENTIAL_STORE", "HISTORY_STORE")
FORBIDDEN = {"recipient_id", "actual_account", "is_dummy", "slot_is_real", "hidden_policy_branch", "private_label"}

SCHEMAS = {
    "SEND_MESSAGE": {
        "object": [("recipient", "read"), ("attachment", "read"), ("sender_identity", "read")],
        "policy": [("recipient_policy", "read"), ("attachment_policy", "read"), ("sender_policy", "read")],
        "credential": [("email_account", "read")],
        "history": [("recipient_disclosure_history", "read"), ("disclosure_record", "write")],
    },
    "SHARE_FILE": {
        "object": [("recipient", "read"), ("document", "read")],
        "policy": [("recipient_policy", "read"), ("document_policy", "read")],
        "credential": [("drive_account", "read")], "history": [("share_record", "write")],
    },
    "CREATE_EVENT": {
        "object": [("attendee", "read"), ("calendar", "read")],
        "policy": [("attendee_policy", "read")],
        "credential": [("calendar_account", "read")], "history": [("invite_record", "write")],
    },
    "BOOK_TRAVEL": {
        "object": [("traveler", "read"), ("profile", "read")],
        "policy": [("travel_policy", "read")],
        "credential": [("travel_account", "read")], "history": [("booking_record", "write")],
    },
}

STORE_FOR = {"object": "OBJECT_STORE", "policy": "POLICY_STORE", "credential": "CREDENTIAL_STORE", "history": "HISTORY_STORE"}

@dataclass(frozen=True)
class Action:
    action_type: str
    recipient: int
    attachment: int | None
    explicit_account: int | None
    policy_branch: int
    history_relevant: bool

@dataclass
class Result:
    concrete_args: dict[str, Any]
    host_visible_trace: list[dict[str, Any]]

class PathORAMTrace:
    """Trace-only idealized Path-ORAM interface, not a payload ORAM.

    Each access exposes a uniformly sampled root-to-leaf path and immediately
    remaps the logical block. The path distribution is therefore independent
    of logical identity in this intended leakage model. Stash, eviction,
    encryption, concurrency, and failure modes are deliberately not modeled.
    """
    def __init__(self, seed: int, depth: int = 5):
        self.rng = random.Random(seed)
        self.depth = depth

    def access(self, store: str, operation: str, order: int) -> dict[str, Any]:
        leaf = self.rng.randrange(1 << self.depth)
        nodes = []
        node = 0
        for level in range(self.depth + 1):
            nodes.append(f"n{level}:{node}")
            if level < self.depth:
                node = node * 2 + 1 + ((leaf >> (self.depth - level - 1)) & 1)
        return {"store": store, "operation": operation, "order": order,
                "path": nodes, "path_length": len(nodes)}

def stable_token(store: str, record: str, encrypted: bool) -> str:
    prefix = "encaddr" if encrypted else "addr"
    digest = hmac.new(b"synthetic-experiment-key", f"{store}:{record}".encode(), hashlib.sha256).hexdigest()[:16]
    return f"{prefix}_{digest}"

def compile_schema(action_type: str) -> tuple[tuple[str, str, str], ...]:
    plan = []
    for category in ("object", "policy", "credential", "history"):
        for slot, op in SCHEMAS[action_type][category]:
            plan.append((STORE_FOR[category], slot, op))
    return tuple(plan)

def dependencies(a: Action) -> list[tuple[str, str, str]]:
    rec = f"CONTACT_{a.recipient}"
    account = a.explicit_account if a.explicit_account is not None else (a.recipient % 4)
    out = [
        ("OBJECT_STORE", rec, "read"),
        ("OBJECT_STORE", f"SENDER_{account}", "read"),
        ("POLICY_STORE", f"POLICY_{rec}_{a.policy_branch}", "read"),
        ("POLICY_STORE", f"SENDER_POLICY_{account}", "read"),
    ]
    if a.attachment is not None:
        out.insert(1, ("OBJECT_STORE", f"DOCUMENT_{a.attachment}", "read"))
        out.insert(-1, ("POLICY_STORE", f"DOCUMENT_POLICY_{a.attachment}", "read"))
    if a.explicit_account is not None:
        out.append(("CREDENTIAL_STORE", f"ACCOUNT_{account}", "read"))
    if a.history_relevant:
        out.append(("HISTORY_STORE", f"DISCLOSURE_HISTORY_{rec}", "read"))
    out.append(("HISTORY_STORE", f"DISCLOSURE_RECORD_{rec}", "write"))
    return out

def concrete(a: Action) -> dict[str, Any]:
    account = a.explicit_account if a.explicit_account is not None else (a.recipient % 4)
    return {
        "operation": "synthetic_send_message",
        "recipient": f"person{a.recipient}@example.invalid",
        "attachment": None if a.attachment is None else f"synthetic_document_{a.attachment}",
        "account": f"synthetic_account_{account}",
        "authorized": True,
    }

def mediate(a: Action, variant: str, seed: int) -> Result:
    deps = dependencies(a)
    trace: list[dict[str, Any]] = []
    if variant in ("V0", "V1"):
        for i, (store, record, op) in enumerate(deps):
            trace.append({"store": store, "record_token": stable_token(store, record, variant == "V1"),
                          "operation": op, "order": i})
    elif variant == "V2":
        oram = PathORAMTrace(seed)
        for i, (store, _record, op) in enumerate(deps):
            trace.append(oram.access(store, op, i))
    elif variant == "V3":
        oram = PathORAMTrace(seed)
        for i, (store, _slot, op) in enumerate(compile_schema(a.action_type)):
            trace.append(oram.access(store, op, i))
    else:
        raise ValueError(variant)
    return Result(concrete(a), trace)

def make_actions(n: int, seed: int) -> list[Action]:
    rng = random.Random(seed)
    actions = []
    # Exactly balanced four occupancy classes; other hidden state is independent.
    patterns = [(False, False), (True, False), (False, True), (True, True)]
    for i in range(n):
        has_attachment, explicit = patterns[i % 4]
        recipient = rng.randrange(16)
        actions.append(Action("SEND_MESSAGE", recipient,
            rng.randrange(32) if has_attachment else None,
            rng.randrange(4) if explicit else None,
            rng.randrange(2), rng.random() < 0.5))
    rng.shuffle(actions)
    return actions

def occupancy(a: Action) -> int:
    return (1 if a.attachment is not None else 0) + (2 if a.explicit_account is not None else 0)

def assert_public_trace(trace: list[dict[str, Any]]) -> None:
    for event in trace:
        overlap = FORBIDDEN.intersection(event)
        if overlap:
            raise AssertionError(f"private fields leaked: {overlap}")

def timed_mediation(actions: list[Action], variant: str, seed: int) -> tuple[float, float]:
    start = time.perf_counter()
    accesses = 0
    for i, a in enumerate(actions):
        accesses += len(mediate(a, variant, seed * 1_000_003 + i).host_visible_trace)
    elapsed = time.perf_counter() - start
    return elapsed * 1e6 / len(actions), accesses / len(actions)
