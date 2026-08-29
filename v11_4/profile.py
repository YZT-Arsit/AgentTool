from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass


PERIOD_CANDIDATES_MS = (10, 20, 25)
HORIZON_CANDIDATES_MS = (2000, 3000, 4000, 5000, 7500, 10000)
PERIOD_QUALIFICATION_HORIZON_MS = 1000

PROFILE_ID = re.compile(
    r"^V11_4-(?P<class>PERIOD-QUAL|HORIZON-QUAL|STRICT-ONLINE)-H(?P<maximum>[1-9][0-9]*)-H(?P<horizon>[1-9][0-9]*)-P(?P<period>[1-9][0-9]*)$"
)


@dataclass(frozen=True)
class OnlinePublicProfileV11_4:
    profile_id: str
    maximum_real_operations: int
    admission_horizon_ms: int
    round_period_ms: int
    provider_completion_bound_ms: int = 50
    terminal_rounds: int = 1
    session_count: int = 1
    request_bhttp_bytes: int = 1024
    response_bhttp_bytes: int = 768
    request_final_bytes: int = 1079
    response_final_bytes: int = 800
    ohttp_key_id: int = 7
    kem_id: int = 0x0020
    kdf_id: int = 0x0001
    aead_id: int = 0x0001
    config_epoch: int = 3
    relay_endpoint_class: str = "LOCAL_RELAY"
    gateway_endpoint_class: str = "LOCAL_GATEWAY"
    connection_policy: str = "ONE_PERSISTENT_HTTP2_CONNECTION_PER_HOP_PER_PUBLIC_SESSION"
    scheduled_start_policy: str = "PUBLIC_SESSION_ACCEPT_MONOTONIC_T0"

    @property
    def admission_rounds(self) -> int:
        return math.ceil(self.admission_horizon_ms / self.round_period_ms)

    @property
    def completion_rounds(self) -> int:
        return math.ceil(self.provider_completion_bound_ms / self.round_period_ms)

    @property
    def result_capacity_rounds(self) -> int:
        return self.maximum_real_operations

    @property
    def total_rounds(self) -> int:
        return self.admission_rounds + self.completion_rounds + self.result_capacity_rounds + self.terminal_rounds

    @property
    def scheduled_lifetime_ms(self) -> int:
        return self.total_rounds * self.round_period_ms

    @property
    def scheduled_lifetime_ns(self) -> int:
        return self.scheduled_lifetime_ms * 1_000_000

    def validate(self) -> "OnlinePublicProfileV11_4":
        match = PROFILE_ID.fullmatch(self.profile_id)
        if match is None:
            raise ValueError("V11.4 profile ID violates the public-only grammar")
        encoded = tuple(int(match.group(name)) for name in ("maximum", "horizon", "period"))
        if encoded != (self.maximum_real_operations, self.admission_horizon_ms, self.round_period_ms):
            raise ValueError("V11.4 profile ID disagrees with public policy fields")
        if self.maximum_real_operations <= 0 or self.admission_horizon_ms <= 0 or self.round_period_ms <= 0:
            raise ValueError("V11.4 public capacity fields must be positive")
        if self.session_count != 1:
            raise ValueError("V11.4 supports exactly one preselected public session")
        if self.provider_completion_bound_ms != 50 or self.terminal_rounds != 1:
            raise ValueError("V11.4 must retain B=50 ms and T=1")
        if self.request_final_bytes != 1079 or self.response_final_bytes != 800:
            raise ValueError("V11.4 must retain the frozen final OHTTP sizes")
        if (self.ohttp_key_id, self.kem_id, self.kdf_id, self.aead_id, self.config_epoch) != (7, 32, 1, 1, 3):
            raise ValueError("V11.4 must retain the frozen public OHTTP suite")
        if self.total_rounds != self.admission_rounds + self.completion_rounds + self.maximum_real_operations + self.terminal_rounds:
            raise AssertionError("V11.4 capacity formula mismatch")
        return self

    def go_plan_fields(self) -> dict[str, int | str]:
        self.validate()
        return {
            "profile_id": self.profile_id,
            "rounds": self.total_rounds,
            "admission_rounds": self.admission_rounds,
            "maximum_real_operations": self.maximum_real_operations,
            "round_period_ms": self.round_period_ms,
            "provider_completion_bound_ms": self.provider_completion_bound_ms,
            "request_bhttp_bytes": self.request_bhttp_bytes,
            "response_bhttp_bytes": self.response_bhttp_bytes,
            "request_final_bytes": self.request_final_bytes,
            "response_final_bytes": self.response_final_bytes,
        }

    def public_schema(self) -> dict[str, object]:
        value = asdict(self)
        value.update(
            {
                "schema": "AgentTool.V11_4OnlinePublicProfile/1",
                "admission_rounds": self.admission_rounds,
                "completion_rounds": self.completion_rounds,
                "result_drain_rounds": self.result_capacity_rounds,
                "total_rounds": self.total_rounds,
                "scheduled_lifetime_ms": self.scheduled_lifetime_ms,
                "scheduled_lifetime_ns": self.scheduled_lifetime_ns,
                "capacity_formula": "R = ceil(H / Delta) + ceil(B / Delta) + M + T",
                "unused_admission_round": "encrypted NOOP",
                "drain_only_request": "encrypted NOOP",
                "unused_response_capacity": "encrypted WAIT",
                "timing_privacy": "OPEN / NOT TESTED",
                "packet_level_timing": "OPEN",
                "hardware_tee": "NOT_TESTED",
            }
        )
        return value


def period_candidate_profiles() -> tuple[OnlinePublicProfileV11_4, ...]:
    return tuple(
        OnlinePublicProfileV11_4(
            profile_id=f"V11_4-PERIOD-QUAL-H1-H{PERIOD_QUALIFICATION_HORIZON_MS}-P{period}",
            maximum_real_operations=1,
            admission_horizon_ms=PERIOD_QUALIFICATION_HORIZON_MS,
            round_period_ms=period,
        ).validate()
        for period in PERIOD_CANDIDATES_MS
    )


def horizon_candidate_profiles(period_ms: int) -> tuple[OnlinePublicProfileV11_4, ...]:
    if period_ms not in PERIOD_CANDIDATES_MS:
        raise ValueError("horizon qualification requires a predeclared selected period")
    return tuple(
        OnlinePublicProfileV11_4(
            profile_id=f"V11_4-HORIZON-QUAL-H50-H{horizon}-P{period_ms}",
            maximum_real_operations=50,
            admission_horizon_ms=horizon,
            round_period_ms=period_ms,
        ).validate()
        for horizon in HORIZON_CANDIDATES_MS
    )


def selected_profile(period_ms: int, horizon_ms: int) -> OnlinePublicProfileV11_4:
    if period_ms not in PERIOD_CANDIDATES_MS or horizon_ms not in HORIZON_CANDIDATES_MS:
        raise ValueError("selected profile must come from the predeclared candidate sets")
    return OnlinePublicProfileV11_4(
        profile_id=f"V11_4-STRICT-ONLINE-H50-H{horizon_ms}-P{period_ms}",
        maximum_real_operations=50,
        admission_horizon_ms=horizon_ms,
        round_period_ms=period_ms,
    ).validate()
