from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .models import AgentServiceSubtype, CanonicalActionFamily, V11ActionCase


# The accepted V10 public profile fixes the inner BHTTP request bucket at 1024
# bytes.  Keep a conservative application-payload admission bound so V11 never
# mutates that public profile in response to private input size.
MAX_PRIVATE_ACTION_PAYLOAD_BYTES = 400


@dataclass(frozen=True)
class PrivateAgentServiceEnvelope:
    protocol_version: int
    agent_service_subtype: AgentServiceSubtype
    arguments: dict[str, Any]
    continuation: dict[str, Any]

    def encode(self) -> bytes:
        return json.dumps(
            {
                "protocol_version": self.protocol_version,
                "agent_service_subtype": self.agent_service_subtype.value,
                "arguments": self.arguments,
                "continuation": self.continuation,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @classmethod
    def decode(cls, value: bytes) -> "PrivateAgentServiceEnvelope":
        decoded = json.loads(value)
        if set(decoded) != {"protocol_version", "agent_service_subtype", "arguments", "continuation"}:
            raise ValueError("invalid private Agent-service envelope")
        return cls(
            int(decoded["protocol_version"]),
            AgentServiceSubtype(decoded["agent_service_subtype"]),
            dict(decoded["arguments"]),
            dict(decoded["continuation"]),
        )


def protected_payload(case: V11ActionCase) -> bytes:
    case.validate()
    if case.action_family is CanonicalActionFamily.AGENT_SERVICE:
        assert case.agent_service_subtype is not None
        encoded = PrivateAgentServiceEnvelope(
            1,
            case.agent_service_subtype,
            case.argument_schema.validate_values(case.arguments),
            case.continuation,
        ).encode()
    else:
        encoded = json.dumps(
            {
                "protocol_version": 1,
                "arguments": case.argument_schema.validate_values(case.arguments),
                "continuation": case.continuation,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    if len(encoded) > MAX_PRIVATE_ACTION_PAYLOAD_BYTES:
        raise ValueError(
            "private action payload exceeds the fixed V11 admission bound; "
            "the frozen public BHTTP bucket is not resized"
        )
    return encoded


def logical_request(case: V11ActionCase) -> dict[str, Any]:
    return {
        "operation_id": case.operation_id,
        "action_family": case.action_family.value,
        "agent_service_subtype": (
            case.agent_service_subtype.value if case.agent_service_subtype is not None else None
        ),
        "arguments": case.argument_schema.validate_values(case.arguments),
    }
