"""V9.1 pre-holdout public-profile hardening.

This package is deliberately separate from :mod:`canonical_v9`: V9 source and
evidence are frozen.  V9.1 changes only how a public schedule is selected and
how its Relay-visible trace is projected.
"""

from .profile import PublicCapacityProfile, strict_h50_profile, validate_profile_id
from .projection import strict_size_projection, strict_structural_projection

__all__ = [
    "PublicCapacityProfile",
    "strict_h50_profile",
    "strict_size_projection",
    "strict_structural_projection",
    "validate_profile_id",
]
