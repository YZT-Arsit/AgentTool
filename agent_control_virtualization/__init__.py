"""Agent-control virtualization feasibility prototype.

ORAM is deliberately absent from this package. Private lookup is an interface;
the bundled backend is explicitly non-cryptographic.
"""

from .ir import AgentCapsule, ControlEvent, ControlRow, Opcode
from .runtime import AgentControlExecutor

__all__ = ["AgentCapsule", "AgentControlExecutor", "ControlEvent", "ControlRow", "Opcode"]
