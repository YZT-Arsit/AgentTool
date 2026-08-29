from __future__ import annotations

import re
from dataclasses import asdict, dataclass


PROFILE_ID = re.compile(r"^V11_3-STRICT-ONLINE-H(?P<maximum>[1-9][0-9]*)-A(?P<admission>[1-9][0-9]*)-P(?P<period>[1-9][0-9]*)$")
CANDIDATE_ADMISSION_ROUNDS = (75, 100, 150, 200, 300)


@dataclass(frozen=True)
class OnlinePublicProfile:
    profile_id: str
    admission_rounds: int
    maximum_real_operations: int = 50
    round_period_ms: int = 5
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
    connection_policy: str = "ONE_PERSISTENT_KEEP_ALIVE_CONNECTION_PER_PUBLIC_SESSION"
    scheduled_start_policy: str = "PUBLIC_SESSION_ACCEPT_MONOTONIC_T0"

    @property
    def completion_rounds(self) -> int:
        return (self.provider_completion_bound_ms + self.round_period_ms - 1) // self.round_period_ms

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

    @property
    def admission_horizon_ms(self) -> int:
        return self.admission_rounds * self.round_period_ms

    def validate(self) -> "OnlinePublicProfile":
        match = PROFILE_ID.fullmatch(self.profile_id)
        if match is None:
            raise ValueError("V11.3 profile ID violates the public-only grammar")
        encoded = tuple(int(match.group(name)) for name in ("maximum", "admission", "period"))
        if encoded != (self.maximum_real_operations, self.admission_rounds, self.round_period_ms):
            raise ValueError("V11.3 profile ID disagrees with public capacity fields")
        if self.admission_rounds < self.maximum_real_operations:
            raise ValueError("online admission rounds are below maximum real operations")
        if self.session_count != 1:
            raise ValueError("V11.3 supports exactly one preselected public session")
        if self.provider_completion_bound_ms <= 0 or self.round_period_ms <= 0:
            raise ValueError("online timing capacity fields must be positive")
        if self.request_final_bytes != 1079 or self.response_final_bytes != 800:
            raise ValueError("V11.3 must retain the frozen final OHTTP sizes")
        if (self.ohttp_key_id, self.kem_id, self.kdf_id, self.aead_id, self.config_epoch) != (7, 32, 1, 1, 3):
            raise ValueError("V11.3 must retain the frozen public OHTTP suite")
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
                "schema": "AgentTool.V11_3OnlinePublicProfile/1",
                "completion_rounds": self.completion_rounds,
                "result_drain_rounds": self.result_capacity_rounds,
                "total_rounds": self.total_rounds,
                "admission_horizon_ms": self.admission_horizon_ms,
                "scheduled_lifetime_ms": self.scheduled_lifetime_ms,
                "scheduled_lifetime_ns": self.scheduled_lifetime_ns,
                "capacity_formula": "R = A + ceil(B_provider / Delta) + M + T",
                "unused_admission_round": "encrypted NOOP",
                "drain_only_request": "encrypted NOOP",
                "unused_response_capacity": "encrypted WAIT",
                "timing_privacy": "OPEN / NOT TESTED",
                "packet_level_timing": "OPEN",
                "hardware_tee": "NOT_TESTED",
            }
        )
        return value


def candidate_profiles() -> tuple[OnlinePublicProfile, ...]:
    return tuple(
        OnlinePublicProfile(profile_id=f"V11_3-STRICT-ONLINE-H50-A{admission}-P5", admission_rounds=admission).validate()
        for admission in CANDIDATE_ADMISSION_ROUNDS
    )
