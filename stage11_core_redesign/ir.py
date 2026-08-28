from __future__ import annotations

from dataclasses import dataclass

from stage9_adaptive.ir import MediationProgram, Visibility, build_program


ROUTING_KINDS = (
    "PARSE_INTENT",
    "SELECT_CAPABILITY",
    "RESOLVE_AGENT",
    "FETCH_AGENT_RECORD",
    "AUTHORIZE_AGENT",
    "PREPARE_DISPATCH",
    "DISPATCH_AGENT",
)


@dataclass(frozen=True)
class AnnotatedOperation:
    kind: str
    visibility: Visibility
    external_effect: bool = False


@dataclass(frozen=True)
class ExtendedMediationIR:
    """A routing front-end composed with the unchanged Stage-9 IR.

    The front-end adds no task-name branch and does not replace the existing
    finite mediation program or AdaptiveNormalizer.
    """

    routing_frontend: tuple[AnnotatedOperation, ...]
    downstream: MediationProgram
    private_values: tuple[str, ...]
    public_values: tuple[str, ...]


def build_extended_ir(scenario: str = "AUTHORIZATION") -> ExtendedMediationIR:
    frontend = (
        AnnotatedOperation("PARSE_INTENT", Visibility.PUBLIC),
        AnnotatedOperation("SELECT_CAPABILITY", Visibility.PUBLIC),
        AnnotatedOperation("RESOLVE_AGENT", Visibility.PRIVATE),
        AnnotatedOperation("FETCH_AGENT_RECORD", Visibility.PRIVATE),
        AnnotatedOperation("AUTHORIZE_AGENT", Visibility.PRIVATE),
        AnnotatedOperation("PREPARE_DISPATCH", Visibility.PRIVATE),
        AnnotatedOperation("DISPATCH_AGENT", Visibility.PRIVATE),
    )
    assert all(operation.kind in ROUTING_KINDS for operation in frontend)
    return ExtendedMediationIR(
        frontend,
        build_program(scenario),
        (
            "concrete_agent_id",
            "registry_index",
            "authorization_exists",
            "provenance_state",
            "approval_occurrence",
            "retry_resume_count",
        ),
        (
            "public_task_projection",
            "capability_class",
            "horizon",
            "cadence_configuration",
            "final_effect_projection",
            "success_class",
        ),
    )
