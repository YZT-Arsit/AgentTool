"""Historical Stage-11 timing/size feasibility components.

The rejected Agent/Tool dispatch implementation has been removed.  The
remaining IR and shaping helpers are not an active invocation-privacy design.
"""

from .ir import build_extended_ir
from .shaping import shape_bounded_trace

__all__ = ["build_extended_ir", "shape_bounded_trace"]
