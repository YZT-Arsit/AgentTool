from __future__ import annotations

from pathlib import Path

from .canonical_bridge import CanonicalSemanticBridge
from .frameworks import run_framework
from .models import CaseSpec, SemanticExecutionRecord, semantic_record
from .providers import run_native_provider


def run_native_case(case_spec: CaseSpec) -> SemanticExecutionRecord:
    """Run the pinned framework with its native action machinery."""

    evidence = run_framework(case_spec.validate(), run_native_provider)
    return semantic_record(evidence, {"execution_path": "PINNED_NATIVE_FRAMEWORK_REFERENCE"})


def run_canonical_case(case_spec: CaseSpec, artifact_root: Path | None = None) -> SemanticExecutionRecord:
    """Run the pinned framework with the accepted canonical outbound bridge."""

    bridge = CanonicalSemanticBridge(artifact_root)
    evidence = run_framework(case_spec.validate(), bridge)
    if len(bridge.runs) != 1:
        raise AssertionError("canonical framework case did not invoke exactly one protected action")
    return semantic_record(evidence, {"execution_path": "PINNED_FRAMEWORK_TO_ACCEPTED_CANONICAL_V9_1", "canonical_bridge": bridge.runs[0]})
