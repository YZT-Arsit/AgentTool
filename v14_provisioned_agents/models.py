from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


REAL_AGENT_ID_LIMIT = 1 << 63
DUMMY_AGENT_ID = (1 << 64) - 1
ARTIFACT_VERSION = 1
PIR_ROW_HANDLE_BYTES = 32


class AgentFramework(StrEnum):
    OPENAI_AGENTS_SDK = "OPENAI_AGENTS_SDK"
    MICROSOFT_AGENT_FRAMEWORK = "MICROSOFT_AGENT_FRAMEWORK"


def validate_agent_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("AgentID must be an integer")
    if not 0 <= value < REAL_AGENT_ID_LIMIT:
        raise ValueError("AgentID overlaps the reserved dummy namespace")
    return value


def _validate_json(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string key")
            if key.lower() in {
                "private_execution_handle",
                "remote_agent_endpoint",
                "agent_service_route",
                "gateway_agent_destination",
            }:
                raise ValueError(f"remote Agent-service field forbidden: {path}.{key}")
            _validate_json(item, f"{path}.{key}")
        return
    raise TypeError(f"{path} contains a non-JSON value")


@dataclass(frozen=True)
class ProvisionedAgentArtifactV1:
    """Deterministic, declarative state needed to reconstruct an Agent in TEE."""

    canonical_agent_id: int
    framework: AgentFramework
    name: str
    instructions: str
    model_reference: str
    model_configuration: dict[str, Any] = field(default_factory=dict)
    tool_capability_refs: tuple[str, ...] = ()
    sub_agent_ids: tuple[int, ...] = ()
    handoff_agent_ids: tuple[int, ...] = ()
    runtime_policy: dict[str, Any] = field(default_factory=dict)
    publisher_id: str = "oae-development-publisher"
    publisher_version: int = 1
    artifact_version: int = ARTIFACT_VERSION
    store_epoch: int = 20260915

    def validated(self) -> "ProvisionedAgentArtifactV1":
        validate_agent_id(self.canonical_agent_id)
        if not isinstance(self.framework, AgentFramework):
            raise ValueError("unsupported Agent framework")
        for name in ("name", "instructions", "model_reference", "publisher_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value.encode()) > 512:
                raise ValueError(f"invalid artifact field {name}")
        if self.artifact_version != ARTIFACT_VERSION:
            raise ValueError("unsupported ProvisionedAgentArtifact version")
        if self.publisher_version < 0 or self.store_epoch < 0:
            raise ValueError("negative artifact version metadata")
        if len(self.tool_capability_refs) > 16:
            raise ValueError("too many tool capability references")
        if len(self.sub_agent_ids) > 8 or len(self.handoff_agent_ids) > 8:
            raise ValueError("too many nested Agent references")
        for reference in (*self.sub_agent_ids, *self.handoff_agent_ids):
            validate_agent_id(reference)
            if reference == self.canonical_agent_id:
                raise ValueError("direct Agent self-reference is forbidden")
        if len(set(self.sub_agent_ids)) != len(self.sub_agent_ids):
            raise ValueError("duplicate sub-Agent reference")
        for capability in self.tool_capability_refs:
            if not capability or len(capability.encode()) > 128:
                raise ValueError("invalid capability reference")
        for name, mapping in (
            ("model_configuration", self.model_configuration),
            ("runtime_policy", self.runtime_policy),
        ):
            _validate_json(mapping, name)
        return self

    def canonical_body(self) -> dict[str, Any]:
        self.validated()
        return {
            "artifact_version": self.artifact_version,
            "canonical_agent_id": self.canonical_agent_id,
            "framework": self.framework.value,
            "handoff_agent_ids": list(self.handoff_agent_ids),
            "instructions": self.instructions,
            "model_configuration": self.model_configuration,
            "model_reference": self.model_reference,
            "name": self.name,
            "publisher_id": self.publisher_id,
            "publisher_version": self.publisher_version,
            "runtime_policy": self.runtime_policy,
            "store_epoch": self.store_epoch,
            "sub_agent_ids": list(self.sub_agent_ids),
            "tool_capability_refs": list(self.tool_capability_refs),
        }

    @classmethod
    def from_body(cls, value: object) -> "ProvisionedAgentArtifactV1":
        if not isinstance(value, dict):
            raise ValueError("artifact body is not an object")
        expected = {
            "artifact_version", "canonical_agent_id", "framework",
            "handoff_agent_ids", "instructions", "model_configuration",
            "model_reference", "name", "publisher_id", "publisher_version",
            "runtime_policy", "store_epoch", "sub_agent_ids",
            "tool_capability_refs",
        }
        if set(value) != expected:
            raise ValueError("artifact body field inventory is not exact")
        return cls(
            canonical_agent_id=int(value["canonical_agent_id"]),
            framework=AgentFramework(str(value["framework"])),
            name=str(value["name"]),
            instructions=str(value["instructions"]),
            model_reference=str(value["model_reference"]),
            model_configuration=dict(value["model_configuration"]),
            tool_capability_refs=tuple(str(x) for x in value["tool_capability_refs"]),
            sub_agent_ids=tuple(int(x) for x in value["sub_agent_ids"]),
            handoff_agent_ids=tuple(int(x) for x in value["handoff_agent_ids"]),
            runtime_policy=dict(value["runtime_policy"]),
            publisher_id=str(value["publisher_id"]),
            publisher_version=int(value["publisher_version"]),
            artifact_version=int(value["artifact_version"]),
            store_epoch=int(value["store_epoch"]),
        ).validated()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


_ROW_HANDLE = struct.Struct(">4sHHQQII")


@dataclass(frozen=True)
class PIRRowHandle:
    row_index: int
    store_epoch: int
    record_version: int = ARTIFACT_VERSION

    def encode(self) -> bytes:
        if not 0 <= self.row_index < 2**64 or not 0 <= self.store_epoch < 2**64:
            raise ValueError("PIR row handle outside unsigned 64-bit domain")
        if self.record_version != ARTIFACT_VERSION:
            raise ValueError("PIR row handle record version is unsupported")
        return _ROW_HANDLE.pack(
            b"OARH", 1, 0, self.row_index, self.store_epoch, self.record_version, 0
        )

    @classmethod
    def decode(cls, value: bytes) -> "PIRRowHandle":
        if len(value) != PIR_ROW_HANDLE_BYTES:
            raise ValueError("invalid PIR row handle width")
        magic, version, flags, row, epoch, record_version, reserved = _ROW_HANDLE.unpack(value)
        if magic != b"OARH" or version != 1 or flags or reserved:
            raise ValueError("invalid PIR row handle format")
        return cls(row, epoch, record_version)
