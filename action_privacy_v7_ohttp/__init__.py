"""V7-OHTTP trusted action-routing model.

This package is deliberately separate from the frozen V6 ActionCell wire.  It
contains only the trusted semantic objects and transport contracts required by
the V7-OHTTP architecture.  No class in this package claims to implement RFC
9458 cryptography.
"""

from .models import (
    ActionKind,
    ActionRouteDescriptor,
    AgentDescriptorV7,
    EffectSemantics,
    PlacementClass,
    ProtectedActionIntent,
    ResolvedAction,
)
from .routing import TrustedActionRouter
from .transport import (
    CanonicalTransportUnavailable,
    KnownLengthBHTTPCodec,
    LegacyDevTransportMarker,
    OHTTPClientBackend,
    OHTTPKeyConfiguration,
    RFC9458BackendUnavailable,
)

__all__ = [
    "ActionKind",
    "ActionRouteDescriptor",
    "AgentDescriptorV7",
    "EffectSemantics",
    "PlacementClass",
    "ProtectedActionIntent",
    "ResolvedAction",
    "TrustedActionRouter",
    "CanonicalTransportUnavailable",
    "KnownLengthBHTTPCodec",
    "LegacyDevTransportMarker",
    "OHTTPClientBackend",
    "OHTTPKeyConfiguration",
    "RFC9458BackendUnavailable",
]
