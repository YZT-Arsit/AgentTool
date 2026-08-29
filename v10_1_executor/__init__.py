"""Frozen-candidate V10.1 execution harness.

This package creates semantic records from actual pinned-framework execution.
It deliberately contains no holdout-selection side effects.
"""

from .models import CaseSpec, SemanticExecutionRecord
from .semantic import run_canonical_case, run_native_case
from .structural import StructuralArmSpec, StructuralExecutionRecord, run_structural_arm

__all__ = [
    "CaseSpec",
    "SemanticExecutionRecord",
    "StructuralArmSpec",
    "StructuralExecutionRecord",
    "run_native_case",
    "run_canonical_case",
    "run_structural_arm",
]
