from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

PROFILE_CLASS = "TIMING_INDISTINGUISHABILITY_PROFILE"
PUBLIC_PERIOD_CANDIDATES_MS = (10, 20, 25)
CAUSAL_HORIZON_CANDIDATES_MS = (4500, 5000, 6000)
PIR_PERIOD_CANDIDATES_MS = (60, 75, 100)
PIR_PUBLIC_EPOCH_CANDIDATES_MS = (6000, 8000, 10000)
PUBLIC_SESSION_LIVENESS_CAP_MS = 60_000
PIR_PUBLIC_EPOCH_MS = 6000
PIR_QUERY_COMPLETION_BOUND_MS = 50
MAX_REAL_AGENT_RESOLUTIONS = 6
DUMMY_DESCRIPTOR_ROW = 999
PIR_INITIAL_LEAD_MS = 25
PROFILE_ID = re.compile(
    r"^V12-TIMING-INDIST-H(?P<maximum>[1-9][0-9]*)-H(?P<horizon>[1-9][0-9]*)-P(?P<period>[1-9][0-9]*)-PIR(?P<pir>[1-9][0-9]*)$"
)
EFFECTIVE_PROFILE_ID = re.compile(
    r"^V12-TIMING-INDIST-V2-H(?P<maximum>[1-9][0-9]*)-H(?P<horizon>[1-9][0-9]*)-P(?P<period>[1-9][0-9]*)-PIR(?P<pir>[1-9][0-9]*)$"
)
EFFECTIVE_PROFILE_V3_ID = re.compile(
    r"^V12-TIMING-INDIST-V3-H(?P<maximum>[1-9][0-9]*)-H(?P<horizon>[1-9][0-9]*)-P(?P<period>[1-9][0-9]*)-PIR(?P<pir>[1-9][0-9]*)$"
)
EFFECTIVE_PROFILE_V4_ID = re.compile(
    r"^V12-TIMING-INDIST-V4-H(?P<maximum>[1-9][0-9]*)-H(?P<horizon>[1-9][0-9]*)-P(?P<period>[1-9][0-9]*)-PIR(?P<pir>[1-9][0-9]*)$"
)
NOMINAL_COMMITMENT_V1 = "NOMINAL_COMMITMENT_V1"
EFFECTIVE_PUBLIC_CLOCK_V2 = "EFFECTIVE_PUBLIC_CLOCK_V2"
EFFECTIVE_PUBLIC_CLOCK_V3 = "EFFECTIVE_PUBLIC_CLOCK_V3"
DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4 = "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4"


@dataclass(frozen=True)
class TimingIndistinguishabilityProfile:
    profile_id: str
    round_period_ms: int
    pir_resolution_period_ms: int
    maximum_real_operations: int = 50
    admission_horizon_ms: int = 3000
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
    connection_policy: str = (
        "ONE_PERSISTENT_HTTP2_CONNECTION_PER_HOP_PER_PUBLIC_SESSION"
    )
    scheduled_start_policy: str = "PUBLIC_SESSION_ACCEPT_MONOTONIC_T0"
    profile_class: str = PROFILE_CLASS
    public_session_liveness_cap_ms: int = PUBLIC_SESSION_LIVENESS_CAP_MS
    pir_public_epoch_ms: int = PIR_PUBLIC_EPOCH_MS
    pir_query_completion_bound_ms: int = PIR_QUERY_COMPLETION_BOUND_MS
    maximum_real_agent_resolutions: int = MAX_REAL_AGENT_RESOLUTIONS
    dummy_descriptor_row: int = DUMMY_DESCRIPTOR_ROW
    pir_initial_lead_ms: int = PIR_INITIAL_LEAD_MS
    timing_semantic_revision: str = NOMINAL_COMMITMENT_V1
    response_preparation_lead_ms: int = 0
    pir_commitment_lead_ms: int = 0
    registry_answer_release_delay_ms: int = 0
    registry_worker_lanes: int = 0
    registry_max_inflight: int = 0

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
        return (
            self.admission_rounds
            + self.completion_rounds
            + self.result_capacity_rounds
            + self.terminal_rounds
        )

    @property
    def scheduled_lifetime_ms(self) -> int:
        return self.total_rounds * self.round_period_ms

    @property
    def scheduled_lifetime_ns(self) -> int:
        return self.scheduled_lifetime_ms * 1_000_000

    @property
    def pir_resolution_opportunities(self) -> int:
        return self.pir_public_epoch_ms // self.pir_resolution_period_ms

    @property
    def pir_real_resolution_arrival_cutoff_ms(self) -> int:
        return (
            self.admission_horizon_ms
            - self.maximum_real_agent_resolutions * self.pir_resolution_period_ms
            - self.pir_query_completion_bound_ms
            - 1
        )

    def validate(self) -> "TimingIndistinguishabilityProfile":
        grammar = {
            NOMINAL_COMMITMENT_V1: PROFILE_ID,
            EFFECTIVE_PUBLIC_CLOCK_V2: EFFECTIVE_PROFILE_ID,
            EFFECTIVE_PUBLIC_CLOCK_V3: EFFECTIVE_PROFILE_V3_ID,
            DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4: EFFECTIVE_PROFILE_V4_ID,
        }.get(self.timing_semantic_revision)
        if grammar is None:
            raise ValueError("unknown V12 timing semantic revision")
        match = grammar.fullmatch(self.profile_id)
        if match is None:
            raise ValueError(
                "V12 timing profile ID violates the distinct public grammar"
            )
        encoded = tuple(
            int(match.group(name)) for name in ("maximum", "horizon", "period", "pir")
        )
        expected = (
            self.maximum_real_operations,
            self.admission_horizon_ms,
            self.round_period_ms,
            self.pir_resolution_period_ms,
        )
        if encoded != expected:
            raise ValueError("V12 timing profile ID disagrees with public fields")
        if self.profile_class != PROFILE_CLASS:
            raise ValueError("V12 timing profile class changed")
        if self.round_period_ms not in PUBLIC_PERIOD_CANDIDATES_MS:
            raise ValueError("public period is outside the predeclared candidates")
        if self.pir_resolution_period_ms not in PIR_PERIOD_CANDIDATES_MS:
            raise ValueError("PIR period is outside the predeclared candidates")
        if self.maximum_real_operations != 50:
            raise ValueError("V12 timing maximum operation capacity changed")
        if self.timing_semantic_revision == NOMINAL_COMMITMENT_V1:
            if self.admission_horizon_ms != 3000:
                raise ValueError("historical V12 timing horizon changed")
        elif self.timing_semantic_revision == EFFECTIVE_PUBLIC_CLOCK_V2:
            if self.admission_horizon_ms not in CAUSAL_HORIZON_CANDIDATES_MS:
                raise ValueError(
                    "V12 causal horizon is outside the predeclared candidates"
                )
            if self.round_period_ms != 10 or self.pir_resolution_period_ms != 60:
                raise ValueError("V12 causal-horizon phase freezes Delta10/PIR60")
        elif self.timing_semantic_revision == EFFECTIVE_PUBLIC_CLOCK_V3:
            if self.admission_horizon_ms != 4500:
                raise ValueError("V12 functional Delta qualification freezes H4500")
            if (
                self.round_period_ms not in (10, 20, 25)
                or self.pir_resolution_period_ms != 60
            ):
                raise ValueError("V12 V3 freezes Delta10/20/25 and PIR60")
        elif self.timing_semantic_revision == DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4:
            if self.admission_horizon_ms != 4500:
                raise ValueError("V12 duplex revision freezes H4500")
            if (
                self.round_period_ms not in (10, 20, 25)
                or self.pir_resolution_period_ms != 60
            ):
                raise ValueError("V12 duplex revision freezes Delta10/20/25 and PIR60")
            if self.response_preparation_lead_ms != 5:
                raise ValueError("V12 duplex response preparation lead changed")
            if self.pir_commitment_lead_ms != 5:
                raise ValueError("V12 duplex PIR commitment lead changed")
            if self.registry_answer_release_delay_ms != 50:
                raise ValueError("V12 duplex Registry answer release delay changed")
            if self.registry_worker_lanes != 1 or self.registry_max_inflight != 100:
                raise ValueError("V12 duplex Registry bounded worker design changed")
        else:
            raise ValueError("unknown V12 timing semantic revision")
        if self.provider_completion_bound_ms != 50 or self.terminal_rounds != 1:
            raise ValueError("V12 timing B/T values changed")
        if self.public_session_liveness_cap_ms != 60_000:
            raise ValueError("V12 timing liveness cap changed")
        if self.pir_public_epoch_ms not in PIR_PUBLIC_EPOCH_CANDIDATES_MS:
            raise ValueError(
                "PIR public epoch is outside the predeclared development candidates"
            )
        if self.pir_public_epoch_ms % self.pir_resolution_period_ms:
            raise ValueError(
                "PIR public epoch must contain an integral fixed opportunity count"
            )
        if (
            self.pir_query_completion_bound_ms != 50
            or self.maximum_real_agent_resolutions != 6
        ):
            raise ValueError("V12 causal PIR capacity contract changed")
        if (
            self.pir_resolution_opportunities <= self.maximum_real_agent_resolutions
            or self.dummy_descriptor_row != 999
        ):
            raise ValueError("V12 fixed PIR schedule changed")
        if self.pir_initial_lead_ms != 25:
            raise ValueError("V12 fixed PIR initial lead changed")
        if self.request_final_bytes != 1079 or self.response_final_bytes != 800:
            raise ValueError("V12 fixed public cell sizes changed")
        if (
            self.ohttp_key_id,
            self.kem_id,
            self.kdf_id,
            self.aead_id,
            self.config_epoch,
        ) != (7, 32, 1, 1, 3):
            raise ValueError("V12 public OHTTP suite changed")
        return self

    def go_plan_fields(self) -> dict[str, int | str]:
        self.validate()
        return {
            "profile_id": self.profile_id,
            "profile_class": self.profile_class,
            "rounds": self.total_rounds,
            "admission_rounds": self.admission_rounds,
            "maximum_real_operations": self.maximum_real_operations,
            "round_period_ms": self.round_period_ms,
            "provider_completion_bound_ms": self.provider_completion_bound_ms,
            "request_bhttp_bytes": self.request_bhttp_bytes,
            "response_bhttp_bytes": self.response_bhttp_bytes,
            "request_final_bytes": self.request_final_bytes,
            "response_final_bytes": self.response_final_bytes,
            "public_session_liveness_cap_ms": self.public_session_liveness_cap_ms,
            "admission_horizon_ms": self.admission_horizon_ms,
            "pir_resolution_period_ms": self.pir_resolution_period_ms,
            "pir_public_epoch_ms": self.pir_public_epoch_ms,
            "pir_resolution_opportunities": self.pir_resolution_opportunities,
            "pir_initial_lead_ms": self.pir_initial_lead_ms,
            "timing_semantic_revision": self.timing_semantic_revision,
            "response_preparation_lead_ms": self.response_preparation_lead_ms,
        }

    def public_schema(self) -> dict[str, object]:
        value = asdict(self)
        value.update(
            {
                "schema": (
                    "AgentTool.V12TimingIndistinguishabilityProfile/4"
                    if self.timing_semantic_revision
                    == DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4
                    else (
                        "AgentTool.V12TimingIndistinguishabilityProfile/3"
                        if self.timing_semantic_revision == EFFECTIVE_PUBLIC_CLOCK_V3
                        else (
                            "AgentTool.V12TimingIndistinguishabilityProfile/2"
                            if self.timing_semantic_revision
                            == EFFECTIVE_PUBLIC_CLOCK_V2
                            else "AgentTool.V12TimingIndistinguishabilityProfile/1"
                        )
                    )
                ),
                "admission_rounds": self.admission_rounds,
                "completion_rounds": self.completion_rounds,
                "result_drain_rounds": self.result_capacity_rounds,
                "total_rounds": self.total_rounds,
                "nominal_lifetime_ms": self.scheduled_lifetime_ms,
                "nominal_lifetime_ns": self.scheduled_lifetime_ns,
                "capacity_formula": "R = ceil(H / Delta) + ceil(B / Delta) + M + T",
                "pir_capacity_formula": "Q = pir_public_epoch_ms / pir_resolution_period_ms",
                "pir_resolution_opportunities": self.pir_resolution_opportunities,
                "pir_real_resolution_arrival_cutoff_ms": self.pir_real_resolution_arrival_cutoff_ms,
                "late_cell_rule": "NO_DROP_NO_BURST_PUBLIC_RECURRENCE",
                "slot_commitment_clock": (
                    "E_i_MINUS_L_FROM_PUBLIC_RECURRENCE"
                    if self.timing_semantic_revision
                    in {
                        EFFECTIVE_PUBLIC_CLOCK_V2,
                        EFFECTIVE_PUBLIC_CLOCK_V3,
                        DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4,
                    }
                    else "D_i_MINUS_L_NOMINAL"
                ),
                "timing_privacy": "OPEN / NOT TESTED",
                "packet_level_timing": "OPEN / NOT TESTED",
                "hardware_tee": "NOT_TESTED",
            }
        )
        return value


def candidate_profiles() -> tuple[TimingIndistinguishabilityProfile, ...]:
    return tuple(
        TimingIndistinguishabilityProfile(
            profile_id=f"V12-TIMING-INDIST-H50-H3000-P{period}-PIR{pir_period}",
            round_period_ms=period,
            pir_resolution_period_ms=pir_period,
        ).validate()
        for period in PUBLIC_PERIOD_CANDIDATES_MS
        for pir_period in PIR_PERIOD_CANDIDATES_MS
    )


def causal_horizon_candidate_profiles() -> tuple[
    TimingIndistinguishabilityProfile, ...
]:
    return tuple(
        TimingIndistinguishabilityProfile(
            profile_id=f"V12-TIMING-INDIST-V2-H50-H{horizon}-P10-PIR60",
            round_period_ms=10,
            pir_resolution_period_ms=60,
            admission_horizon_ms=horizon,
            timing_semantic_revision=EFFECTIVE_PUBLIC_CLOCK_V2,
        ).validate()
        for horizon in CAUSAL_HORIZON_CANDIDATES_MS
    )


def delta_functional_candidate_profiles() -> tuple[
    TimingIndistinguishabilityProfile, ...
]:
    return tuple(
        TimingIndistinguishabilityProfile(
            profile_id=f"V12-TIMING-INDIST-V3-H50-H4500-P{period}-PIR60",
            round_period_ms=period,
            pir_resolution_period_ms=60,
            admission_horizon_ms=4500,
            timing_semantic_revision=EFFECTIVE_PUBLIC_CLOCK_V3,
        ).validate()
        for period in (10, 20, 25)
    )


def duplex_timing_candidate_profiles() -> tuple[TimingIndistinguishabilityProfile, ...]:
    return tuple(
        TimingIndistinguishabilityProfile(
            profile_id=f"V12-TIMING-INDIST-V4-H50-H4500-P{period}-PIR60",
            round_period_ms=period,
            pir_resolution_period_ms=60,
            admission_horizon_ms=4500,
            timing_semantic_revision=DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4,
            response_preparation_lead_ms=5,
            pir_commitment_lead_ms=5,
            registry_answer_release_delay_ms=50,
            registry_worker_lanes=1,
            registry_max_inflight=100,
        ).validate()
        for period in (10, 20, 25)
    )
