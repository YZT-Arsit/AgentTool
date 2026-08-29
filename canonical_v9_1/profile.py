from __future__ import annotations

import re
from dataclasses import asdict, dataclass


STRICT_PROFILE_ID = re.compile(r"^V9_1-STRICT-H(?P<capacity>[1-9][0-9]*)-P(?P<revision>[1-9][0-9]*)$")


def validate_profile_id(profile_id: str, maximum_real_operations: int) -> None:
    """Accept only a mechanically public STRICT identifier.

    The grammar has no free-form workload component.  ``H`` is the public
    admission capacity and ``P`` is the public profile revision.  Agent, Tool,
    route, provider, workload-arm and actual-count strings therefore cannot be
    encoded, even accidentally.
    """

    match = STRICT_PROFILE_ID.fullmatch(profile_id)
    if match is None:
        raise ValueError("STRICT profile ID violates the public-only grammar")
    if int(match.group("capacity")) != maximum_real_operations:
        raise ValueError("STRICT profile ID capacity disagrees with the public maximum")


@dataclass(frozen=True)
class PublicCapacityProfile:
    profile_id: str
    public_profile_revision: int
    admission_rounds: int
    maximum_real_operations: int
    total_rounds: int
    round_period_ms: int
    provider_completion_bound_ms: int
    terminal_rounds: int
    session_count: int
    request_bhttp_bytes: int
    response_bhttp_bytes: int
    request_final_bytes: int
    response_final_bytes: int
    ohttp_key_id: int
    kem_id: int
    kdf_id: int
    aead_id: int
    config_epoch: int
    relay_endpoint_class: str
    gateway_endpoint_class: str
    connection_policy: str
    scheduled_start_policy: str

    @property
    def completion_rounds(self) -> int:
        return (self.provider_completion_bound_ms + self.round_period_ms - 1) // self.round_period_ms

    @property
    def result_capacity_rounds(self) -> int:
        return self.maximum_real_operations

    @property
    def scheduled_lifetime_ns(self) -> int:
        return self.total_rounds * self.round_period_ms * 1_000_000

    def validate(self) -> "PublicCapacityProfile":
        validate_profile_id(self.profile_id, self.maximum_real_operations)
        positive = (
            self.admission_rounds,
            self.maximum_real_operations,
            self.total_rounds,
            self.round_period_ms,
            self.provider_completion_bound_ms,
            self.terminal_rounds,
            self.session_count,
            self.request_bhttp_bytes,
            self.response_bhttp_bytes,
            self.request_final_bytes,
            self.response_final_bytes,
        )
        if any(value < 1 for value in positive):
            raise ValueError("public profile fields must be positive")
        if self.session_count != 1:
            raise ValueError("canonical V9.1 runner currently supports one predeclared public session")
        if self.admission_rounds < self.maximum_real_operations:
            raise ValueError("admission rounds are below the public operation capacity")
        required = (
            self.admission_rounds
            + self.completion_rounds
            + self.result_capacity_rounds
            + self.terminal_rounds
        )
        if self.total_rounds < required:
            raise ValueError("public round budget cannot drain the admitted maximum")
        if self.request_final_bytes != 1079 or self.response_final_bytes != 800:
            raise ValueError("V9.1 fixed-size profile must retain measured V9 OHTTP sizes")
        if not all(
            (
                self.relay_endpoint_class,
                self.gateway_endpoint_class,
                self.connection_policy,
                self.scheduled_start_policy,
            )
        ):
            raise ValueError("public endpoint/lifetime policy is incomplete")
        return self

    def admit(self, actual_real_actions: int) -> None:
        if actual_real_actions < 0:
            raise ValueError("actual action count cannot be negative")
        if actual_real_actions > self.maximum_real_operations:
            raise OverflowError("private actions exceed the preselected public capacity")

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
        result = asdict(self)
        result.update(
            {
                "completion_rounds": self.completion_rounds,
                "result_capacity_rounds": self.result_capacity_rounds,
                "scheduled_lifetime_ns": self.scheduled_lifetime_ns,
                "scheduled_end_policy": "scheduled_start + scheduled_lifetime_ns",
                "unused_admission_slot": "encrypted NOOP",
                "unused_result_capacity": "encrypted WAIT",
            }
        )
        return result


def strict_h50_profile() -> PublicCapacityProfile:
    maximum = 50
    admission = 50
    period_ms = 5
    completion_bound_ms = 50
    completion_rounds = (completion_bound_ms + period_ms - 1) // period_ms
    terminal = 1
    total = admission + completion_rounds + maximum + terminal
    return PublicCapacityProfile(
        profile_id="V9_1-STRICT-H50-P1",
        public_profile_revision=1,
        admission_rounds=admission,
        maximum_real_operations=maximum,
        total_rounds=total,
        round_period_ms=period_ms,
        provider_completion_bound_ms=completion_bound_ms,
        terminal_rounds=terminal,
        session_count=1,
        request_bhttp_bytes=1024,
        response_bhttp_bytes=768,
        request_final_bytes=1079,
        response_final_bytes=800,
        ohttp_key_id=7,
        kem_id=0x0020,
        kdf_id=0x0001,
        aead_id=0x0001,
        config_epoch=3,
        relay_endpoint_class="LOCAL_RELAY",
        gateway_endpoint_class="LOCAL_GATEWAY",
        connection_policy="ONE_PERSISTENT_KEEP_ALIVE_CONNECTION_PER_PUBLIC_SESSION",
        scheduled_start_policy="PUBLIC_SESSION_ACCEPT_MONOTONIC_T0",
    ).validate()
