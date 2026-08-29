from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from canonical_v9_1.profile import PublicCapacityProfile
from canonical_v9_1.projection import strict_size_projection, strict_structural_projection

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = "V10-STRICT-H50-C1"
MAX_OPERATION_ID_BYTES = 32
SEMANTIC_FIELDS = (
    "selected_logical_action",
    "arguments",
    "provider_visible_logical_request",
    "effect_count",
    "operation_outcome_semantics",
    "result",
    "final_framework_visible_result_state",
)


class V10PublicCapacityProfile(PublicCapacityProfile):
    """Confirmatory metadata wrapper over the accepted V9.1 security values.

    V9.1 intentionally froze a revision-specific profile-ID grammar.  V10
    changes only the public experiment identifier, so this adapter validates
    the new fixed identifier and then applies every substantive V9.1 check via
    an equivalent temporary V9.1 identifier.  The accepted runner and schedule
    implementation are unchanged.
    """

    def validate(self) -> "V10PublicCapacityProfile":
        if self.profile_id != PROFILE_ID or self.maximum_real_operations != 50:
            raise ValueError("not the frozen V10 confirmatory profile")
        baseline = PublicCapacityProfile(**{**self.__dict__, "profile_id": "V9_1-STRICT-H50-P1"})
        baseline.validate()
        return self


def load_v10_profile(path: Path = ROOT / "PUBLIC_PROFILE_V10.json") -> V10PublicCapacityProfile:
    value = load_json(path)
    value["request_final_bytes"] = value["final_request_bytes"]
    value["response_final_bytes"] = value["final_response_bytes"]
    fields = set(PublicCapacityProfile.__dataclass_fields__)
    return V10PublicCapacityProfile(**{key: value[key] for key in fields}).validate()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_operation_ids(ids: list[str]) -> None:
    if len(ids) != len(set(ids)):
        raise ValueError("operation IDs are not unique within the experiment arm")
    for value in ids:
        encoded = value.encode("utf-8")
        if not value or len(encoded) > MAX_OPERATION_ID_BYTES:
            raise ValueError("operation ID does not fit the canonical 32-byte ABI")
        if encoded.decode("utf-8") != value:
            raise AssertionError("operation ID UTF-8 round trip failed")


def validate_freeze_manifests(semantic: dict[str, Any], structural: dict[str, Any]) -> None:
    if semantic.get("selected_holdout_executed") is not False:
        raise ValueError("semantic manifest is not freeze-only")
    if structural.get("selected_holdout_executed") is not False:
        raise ValueError("structural manifest is not freeze-only")
    for case in semantic["cases"]:
        if case["public_profile_id"] != PROFILE_ID:
            raise ValueError("semantic case uses another public profile")
        validate_operation_ids(case["operation_ids"])
    for pair in structural["pairs"]:
        for arm in pair["arms"]:
            if arm["public_profile_id"] != PROFILE_ID:
                raise ValueError("structural arm uses another public profile")
            validate_operation_ids([a["operation_id"] for a in arm["private_actions"]])


def semantic_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record[field] for field in SEMANTIC_FIELDS}


def compare_semantic(native: dict[str, Any] | None, canonical: dict[str, Any] | None) -> str:
    if native is None:
        return "NATIVE_REFERENCE_FAIL"
    if canonical is None:
        return "CANONICAL_FUNCTIONAL_FAIL"
    return "PASS" if semantic_projection(native) == semantic_projection(canonical) else "SEMANTIC_MISMATCH"


def compare_structural_pair(
    trace_a: dict[str, Any], trace_b: dict[str, Any], profile: PublicCapacityProfile,
    functional_a: bool, functional_b: bool,
) -> dict[str, Any]:
    if not functional_a or not functional_b:
        return {"pair_status": "INVALID_FUNCTIONAL_PAIR", "structural": None, "size": None}
    structural_equal = strict_structural_projection(trace_a, profile) == strict_structural_projection(trace_b, profile)
    size_equal = strict_size_projection(trace_a, profile) == strict_size_projection(trace_b, profile)
    return {"pair_status": "VALID", "structural": "PASS" if structural_equal else "FAIL", "size": "PASS" if size_equal else "FAIL"}


def prefix_projection(projection: dict[str, Any], rounds: int) -> dict[str, Any]:
    sequence_keys = {
        "profile_id_sequence", "selected_public_ohttp_key_id", "kem", "kdf", "aead",
        "config_epoch", "relay_endpoint_class", "gateway_endpoint_class", "session_association",
        "round_order", "request_length_sequence", "response_length_sequence",
        "request_final_bytes", "response_final_bytes",
    }
    return {key: (value[:rounds] if key in sequence_keys else value) for key, value in projection.items()}


def invoke_frozen_runner(plan: Path, output: Path, binary: Path, authorization: Path) -> subprocess.CompletedProcess[str]:
    """Future V10B entrypoint. V10A intentionally ships without authorization."""
    token = load_json(authorization)
    if token.get("phase") != "V10B" or token.get("approved") is not True:
        raise PermissionError("selected holdout execution requires an independently supplied V10B authorization")
    return subprocess.run([str(binary), "--plan", str(plan), "--output", str(output)], check=True, text=True, capture_output=True)
