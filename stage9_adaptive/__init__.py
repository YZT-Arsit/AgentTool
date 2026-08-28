"""Stage-9 bounded adaptive mediation validation.

The package is a local synthetic research prototype, not a production security
runtime.  Its public surface is intentionally small so tests can inspect the IR,
compiler, and execution semantics directly.
"""

from .ir import (
    Guard,
    IROperation,
    MediationProgram,
    Transition,
    Visibility,
    build_program,
)
from .runtime import (
    AdaptiveNormalizer,
    Episode,
    MediationExecutor,
    PrivateMediationState,
    PublicTask,
)

__all__ = [
    "AdaptiveNormalizer",
    "Episode",
    "Guard",
    "IROperation",
    "MediationExecutor",
    "MediationProgram",
    "PrivateMediationState",
    "PublicTask",
    "Transition",
    "Visibility",
    "build_program",
]
