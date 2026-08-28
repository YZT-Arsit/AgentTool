"""Canonical V6 action-metadata privacy substrate.

This package intentionally has no dependency on Agent Control IR.
"""

from .descriptor import AgentDescriptorV6, DescriptorCodec, PlacementClass
from .bootstrap import V6ProvisionedKeys, bootstrap_local_v6
from .models import ActionCellV6, ActionKind, ProtectedActionIntent
from .resolution import ResolutionMode, V6Resolver
from .trusted_module import LocalTrustedBackend, TrustedActionModule

__all__ = [
    "ActionCellV6", "ActionKind", "AgentDescriptorV6", "DescriptorCodec",
    "LocalTrustedBackend", "PlacementClass", "ProtectedActionIntent",
    "ResolutionMode", "TrustedActionModule", "V6ProvisionedKeys", "V6Resolver",
    "bootstrap_local_v6",
]
