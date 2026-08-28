from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PrivacyProfile(StrEnum):
    STRICT = "STRICT"
    CONFIDENTIAL_ENTERPRISE = "CONFIDENTIAL_ENTERPRISE"
    ENTERPRISE_EFFICIENT = "ENTERPRISE_EFFICIENT"


class RouteClass(StrEnum):
    ENTERPRISE = "ENTERPRISE"
    EXTERNAL = "EXTERNAL"


class ToolPlacement(StrEnum):
    TEE_LOCAL = "TEE_LOCAL"
    CLOUD_LOCAL = "CLOUD_LOCAL"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class ProfilePolicy:
    profile: PrivacyProfile
    reveal_route_class: bool
    reveal_internal_tool_category: bool
    common_outer_route: bool
    hide_action_type: bool
    hide_external_destination_from_agent_cloud: bool

    @classmethod
    def for_profile(cls, profile: PrivacyProfile) -> "ProfilePolicy":
        if profile is PrivacyProfile.STRICT:
            return cls(profile, False, False, True, True, True)
        if profile is PrivacyProfile.CONFIDENTIAL_ENTERPRISE:
            return cls(profile, True, False, False, False, False)
        if profile is PrivacyProfile.ENTERPRISE_EFFICIENT:
            return cls(profile, True, True, False, False, False)
        raise ValueError(f"unsupported profile: {profile}")

    def public_route(self, route: RouteClass) -> str:
        return route.value if self.reveal_route_class else "OPAQUE_COMMON_ROUTE"

    def validate_tool_path(self, placement: ToolPlacement, *,
                           through_common_gateway: bool,
                           through_confidential_broker: bool,
                           declared_category: str = "") -> None:
        """Fail closed when a profile would overclaim Tool-identity privacy."""
        if self.profile is PrivacyProfile.STRICT and placement is ToolPlacement.CLOUD_LOCAL:
            if not (through_common_gateway or through_confidential_broker):
                raise PermissionError(
                    "STRICT rejects visible CLOUD_LOCAL Tool activation; use TEE_LOCAL, "
                    "a confidential/common broker, or the CommonActionGateway"
                )
        if self.profile is PrivacyProfile.ENTERPRISE_EFFICIENT:
            if placement is ToolPlacement.CLOUD_LOCAL and not declared_category:
                raise ValueError("ENTERPRISE_EFFICIENT requires an explicit public Tool category")

    def leakage(self) -> tuple[str, ...]:
        base = ("profile", "public_horizon", "frame_bucket", "public_outcome_class")
        if self.profile is PrivacyProfile.STRICT:
            return base
        if self.profile is PrivacyProfile.CONFIDENTIAL_ENTERPRISE:
            return base + ("route_class", "action_class_if_endpoint_visible")
        return base + ("route_class", "declared_internal_tool_category", "action_class")
