# IR-v2 semantic fidelity report

## Result

| Version | Exact matches | Fidelity | Tool-workflow fidelity |
| --- | ---: | ---: | ---: |
| IR-v1 historical baseline | 54/72 | 75.0% | 0/18 (0%) |
| IR-v2 core repair | **72/72** | **100.0%** | **18/18 (100.0%)** |

The 72 cases and seeds are unchanged: 18 OpenAI simple, 18 OpenAI Model→Tool→Model, 18 OpenAI logical handoff, and 18 Microsoft simple executions, seeds 0–17. No failed IR-v1 case was removed.

## Exact projection

IR-v2 compares:

- selected Tool sequence;
- canonical structured Tool arguments;
- Tool call IDs;
- Tool results;
- normalized next-model input after Tool result or handoff reinsertion;
- handoff targets;
- branch choices;
- runtime state transitions;
- actual local Tool invocation/effect sequence and count;
- termination class;
- sanitized final result;
- model-call count.

Every field matched in `SEMANTIC_FIDELITY_V2_RESULTS.csv`; `mismatched_fields` is empty for all 72 rows.

## What changed

IR-v1 compiled a Tool target handle but discarded arguments, did not execute the Tool in its semantic projection, omitted the Tool result, and returned without a post-Tool model call. IR-v2 adds a bounded interpreter with structured `ToolCall(name, arguments, call_id)`, private argument/result storage, exact-once call-ID handling, Tool-result context reinsertion, repeated `MODEL_RESUME`, final output, and explicit error/bound states.

## Evidence boundary

The model responses are deterministic local `ScriptedModel` outputs, while the native paths execute the pinned OpenAI Agents SDK and Microsoft Agent Framework objects. The compiled path uses the same semantic decisions and local Tool implementation through the small framework-neutral interpreter. This is exact deterministic fidelity evidence, not a real-model quality result and not corpus-wide executable coverage.

Multiple sequential Tool rounds, duplicate operation IDs, Tool timeout/error reinsertion, and bound exhaustion are additionally covered by `tests/test_agent_ir_v2.py`; they are engineering tests rather than additions to the frozen 72-case metric.
