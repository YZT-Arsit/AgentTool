from __future__ import annotations

"""Framework-native objects used for the control-plane coverage audit.

The objects below are instantiated from the checked-out public framework
packages.  They are never run against a model or an external service.
"""

from typing import Any

from .compiler import Behavior, Disposition, FrameworkWorkload


def _openai_workloads() -> list[FrameworkWorkload]:
    from agents import Agent, function_tool

    @function_tool
    def lookup_faq(topic: str) -> str:
        """Look up a synthetic FAQ."""
        return f"faq:{topic}"

    @function_tool
    def update_seat(seat: str) -> str:
        """Update a synthetic seat assignment."""
        return f"seat:{seat}"

    @function_tool
    def multiply(a: int, b: int) -> int:
        """Multiply two integers."""
        return a * b

    french = Agent(name="French agent", instructions="Reply in French.")
    spanish = Agent(name="Spanish agent", instructions="Reply in Spanish.")
    english = Agent(name="English agent", instructions="Reply in English.")
    triage = Agent(
        name="Triage agent",
        instructions="Route to the matching language specialist.",
        handoffs=[french, spanish, english],
    )

    faq = Agent(name="FAQ agent", instructions="Answer synthetic FAQs.", tools=[lookup_faq])
    seat = Agent(name="Seat agent", instructions="Change a synthetic seat.", tools=[update_seat])
    service = Agent(
        name="Customer-service triage",
        instructions="Route FAQ and seat requests.",
        handoffs=[faq, seat],
    )
    # Return-to-triage handoffs are native SDK objects, not experiment labels.
    faq.handoffs = [service]
    seat.handoffs = [service]

    calculator = Agent(name="Calculator", instructions="Use the multiply tool.", tools=[multiply])
    lifecycle = Agent(
        name="Lifecycle router",
        instructions="Delegate arithmetic work.",
        handoffs=[calculator],
    )

    translator_es = Agent(name="Spanish translator", instructions="Translate to Spanish.")
    translator_fr = Agent(name="French translator", instructions="Translate to French.")
    manager = Agent(
        name="Translation manager",
        instructions="Use both translators.",
        tools=[
            translator_es.as_tool(tool_name="translate_spanish", tool_description="Translate to Spanish"),
            translator_fr.as_tool(tool_name="translate_french", tool_description="Translate to French"),
        ],
    )

    async def dynamic_instructions(context: Any, agent: Agent[Any]) -> str:
        return f"Dynamic instructions for {agent.name}"

    dynamic = Agent(name="Dynamic prompt agent", instructions=dynamic_instructions)

    common = {
        "framework": "OpenAI Agents SDK",
        "native_object_types": ["agents.agent.Agent", "agents.tool.FunctionTool", "agents.handoffs.Handoff"],
    }
    return [
        FrameworkWorkload(
            name="openai-language-routing",
            source="external_stage10/openai-agents-python/examples/agent_patterns/routing.py",
            agents=[triage, french, spanish, english],
            **common,
        ),
        FrameworkWorkload(
            name="openai-customer-service",
            source="external_stage10/openai-agents-python/examples/customer_service/main.py",
            agents=[service, faq, seat],
            **common,
        ),
        FrameworkWorkload(
            name="openai-agent-lifecycle",
            source="external_stage10/openai-agents-python/examples/basic/agent_lifecycle_example.py",
            agents=[lifecycle, calculator],
            extra_behaviors=[Behavior(
                "lifecycle:prompt_encoded_conditional", "prompt_control", Disposition.UNSUPPORTED,
                "natural-language conditional is not a declarative control edge",
            )],
            **common,
        ),
        FrameworkWorkload(
            name="openai-agents-as-tools",
            source="external_stage10/openai-agents-python/examples/agent_patterns/agents_as_tools.py",
            agents=[manager, translator_es, translator_fr],
            **common,
        ),
        FrameworkWorkload(
            name="openai-dynamic-instructions",
            source="external_stage10/openai-agents-python/examples/basic/dynamic_system_prompt.py",
            agents=[dynamic],
            **common,
        ),
    ]


class _LocalMicrosoftClient:
    """Constructor-only local stand-in; no model call is made."""

    model = "local-no-network-model"


def _microsoft_workloads() -> list[FrameworkWorkload]:
    from agent_framework import Agent, WorkflowBuilder

    def lookup_document(name: str) -> str:
        return f"synthetic:{name}"

    client = _LocalMicrosoftClient()
    helper = Agent(client, name="Helper", instructions="Answer locally.", tools=[lookup_document])

    writer = Agent(client, name="Writer", instructions="Draft text.")
    reviewer = Agent(client, name="Reviewer", instructions="Review text.")
    publisher = Agent(client, name="Publisher", instructions="Return approved text.")
    chain = WorkflowBuilder(start_executor=writer).add_edge(writer, reviewer).add_edge(reviewer, publisher).build()

    classify = Agent(client, name="Classifier", instructions="Classify a request.")
    responder = Agent(client, name="Responder", instructions="Respond after classification.")
    conditional = WorkflowBuilder(start_executor=classify).add_edge(
        classify, responder, condition=lambda value: bool(value)
    ).build()

    planner = Agent(client, name="Planner", instructions="Plan work.")
    analyst = Agent(client, name="Analyst", instructions="Analyze work.")
    summarizer = Agent(client, name="Summarizer", instructions="Summarize work.")
    fanout = WorkflowBuilder(start_executor=planner).add_fan_out_edges(planner, [analyst, summarizer]).build()

    common = {
        "framework": "Microsoft Agent Framework",
        "native_object_types": [
            "agent_framework.Agent", "agent_framework.WorkflowBuilder", "agent_framework.Workflow"
        ],
    }
    return [
        FrameworkWorkload(
            name="microsoft-simple-tool",
            source="external_stage9/agent-framework/python/packages/core/tests/agents/test_agent.py",
            agents=[helper],
            **common,
        ),
        FrameworkWorkload(
            name="microsoft-sequential-workflow",
            source="external_stage9/agent-framework/python/packages/core/tests/workflow/test_workflow_builder.py",
            agents=[writer, reviewer, publisher],
            unconditional_edges=[(0, 1), (1, 2)],
            native_object_types=common["native_object_types"] + [type(chain).__module__ + "." + type(chain).__name__],
            framework=common["framework"],
        ),
        FrameworkWorkload(
            name="microsoft-conditional-workflow",
            source="external_stage9/agent-framework/python/packages/core/tests/workflow/test_workflow_builder.py",
            agents=[classify, responder],
            conditional_edges=[(0, 1)],
            native_object_types=common["native_object_types"] + [type(conditional).__module__ + "." + type(conditional).__name__],
            framework=common["framework"],
        ),
        FrameworkWorkload(
            name="microsoft-fanout-workflow",
            source="external_stage9/agent-framework/python/packages/core/tests/workflow/test_workflow_builder.py",
            agents=[planner, analyst, summarizer],
            fanout_edges=[(0, (1, 2))],
            native_object_types=common["native_object_types"] + [type(fanout).__module__ + "." + type(fanout).__name__],
            framework=common["framework"],
        ),
    ]


def framework_workloads() -> list[FrameworkWorkload]:
    return _openai_workloads() + _microsoft_workloads()
