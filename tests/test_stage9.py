import inspect
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from stage9_adaptive.ir import Visibility, build_program
from stage9_adaptive.runtime import (
    FORBIDDEN_TRACE_FIELDS,
    SCENARIOS,
    TASKS,
    VARIANTS,
    AdaptiveNormalizer,
    MediationExecutor,
    PrivateMediationState,
    Episode,
    PublicTask,
    assert_public_trace,
    make_paired_episode,
    run_dynamic_planning_example,
)


ROOT = Path(__file__).resolve().parents[1]


class Stage9AdaptiveTests(unittest.TestCase):
    def execute_pair(self, scenario, task="SEND_MESSAGE", variant="B2-ADAPTIVE-OBLIVIOUS", horizon=5):
        episodes = [make_paired_episode(branch, scenario, task, branch, 7, 2) for branch in (0, 1)]
        return [MediationExecutor(variant, horizon, 100 + branch).execute(episode) for branch, episode in enumerate(episodes)]

    def test_ir_has_private_and_public_annotations(self):
        for scenario in SCENARIOS:
            program = build_program(scenario)
            guards = [transition.guard for transition in program.transitions]
            operations = [operation for transition in program.transitions for operation in transition.operations]
            self.assertTrue(any(guard.visibility == Visibility.PRIVATE for guard in guards))
            self.assertTrue(any(guard.visibility == Visibility.PUBLIC for guard in guards))
            self.assertTrue(any(operation.visibility == Visibility.PRIVATE for operation in operations))
            self.assertTrue(any(operation.visibility == Visibility.PUBLIC for operation in operations))

    def test_compiler_is_shared_and_task_agnostic(self):
        source = inspect.getsource(AdaptiveNormalizer.compile)
        self.assertNotIn("SEND_MESSAGE", source)
        self.assertNotIn("SHARE_DOCUMENT", source)
        compiler = AdaptiveNormalizer()
        for scenario in SCENARIOS:
            plan = compiler.compile(build_program(scenario), 5)
            self.assertEqual(plan.horizon, 5)
            self.assertFalse(plan.overflow)
            self.assertEqual(plan.public_commit_round, 5)

    def test_per_action_privacy_does_not_imply_trajectory_privacy(self):
        for scenario in SCENARIOS:
            (existing, existing_trace, _), (private_followup, followup_trace, _) = self.execute_pair(scenario, variant="B1-PER-ACTION-OBLIVIOUS")
            self.assertEqual(existing["effect"], private_followup["effect"])
            self.assertNotEqual(existing["visible_rounds"], private_followup["visible_rounds"])
            # Every internal round has the same canonical three-access shape.
            for trace in (existing_trace, followup_trace):
                state_events = [event for event in trace if event["destination_service"] == "PRIVATE_STATE_ORAM"]
                counts = {round_index: sum(event["round"] == round_index for event in state_events) for round_index in {event["round"] for event in state_events}}
                self.assertTrue(all(count == 3 for count in counts.values()))

    def test_b2_structural_trace_equality_for_all_scenarios_and_tasks(self):
        shape = lambda trace: [(event["round"], event["destination_service"], event["operation_class"], event["request_bytes"], event["response_bytes"]) for event in trace]
        for scenario in SCENARIOS:
            for task in TASKS:
                (result_a, trace_a, _), (result_b, trace_b, _) = self.execute_pair(scenario, task)
                self.assertEqual(shape(trace_a), shape(trace_b), (scenario, task))
                self.assertEqual(result_a["visible_rounds"], 5)
                self.assertEqual(result_b["visible_rounds"], 5)

    def test_functional_equivalence_and_same_final_effect(self):
        semantic_fields = ("authorized", "effect_count", "effect", "permission_exists", "provenance_exists", "requires_extra_verification", "sanitized_response", "final_outcome")
        for scenario in SCENARIOS:
            for task in TASKS:
                outputs = {}
                for branch in (0, 1):
                    episode = make_paired_episode(branch, scenario, task, branch, 11, 1)
                    outputs[branch] = [MediationExecutor(variant, 5, 200 + index).execute(episode)[0] for index, variant in enumerate(VARIANTS)]
                    baseline = outputs[branch][0]
                    self.assertTrue(all(all(candidate[field] == baseline[field] for field in semantic_fields) for candidate in outputs[branch][1:]))
                self.assertTrue(all(outputs[0][0][field] == outputs[1][0][field] for field in semantic_fields))

    def test_no_dummy_external_effects(self):
        for scenario in SCENARIOS:
            for branch in (0, 1):
                episode = make_paired_episode(branch, scenario, "SHARE_DOCUMENT", branch, 4, 0)
                for variant in VARIANTS:
                    result, trace, private = MediationExecutor(variant, 5, 300 + branch).execute(episode)
                    self.assertEqual(result["effect_count"], 1)
                    self.assertEqual(sum(event["operation_class"] == "PUBLIC_EFFECT" for event in trace), 1)
                    self.assertTrue(all(item.get("semantic_key", "").startswith(("real:", "pad:", "commit-pad:", "overflow:")) for item in private))

    def test_authorization_deny_never_becomes_effect(self):
        state = PrivateMediationState(7, 2, permission_exists=False, local_consent_grants=False)
        episode = Episode(1, "AUTHORIZATION", PublicTask("SEND_MESSAGE", "CONTACT_7", "DOCUMENT_1"), state)
        for variant in VARIANTS:
            result, trace, _ = MediationExecutor(variant, 5, 401).execute(episode)
            self.assertFalse(result["authorized"])
            self.assertEqual(result["effect_count"], 0)
            self.assertFalse(any(event["operation_class"] == "PUBLIC_EFFECT" for event in trace))

    def test_horizon_overflow_fails_closed_for_whole_class(self):
        traces = []
        for branch in (0, 1):
            episode = make_paired_episode(branch, "AUTHORIZATION", "SEND_MESSAGE", branch, 3, 1)
            result, trace, _ = MediationExecutor("B2-ADAPTIVE-OBLIVIOUS", 3, 500 + branch).execute(episode)
            self.assertTrue(result["overflow"])
            self.assertEqual(result["final_outcome"], "HORIZON_EXCEEDED")
            self.assertEqual(result["effect_count"], 0)
            traces.append(trace)
        shape = lambda trace: [(event["round"], event["destination_service"], event["operation_class"], event["request_bytes"], event["response_bytes"]) for event in trace]
        self.assertEqual(shape(traces[0]), shape(traces[1]))

    def test_host_trace_private_separation(self):
        result, trace, private = self.execute_pair("AUTHORIZATION")[1]
        assert_public_trace(trace)
        encoded = json.dumps(trace)
        for field in FORBIDDEN_TRACE_FIELDS:
            self.assertNotIn(field, encoded)
        self.assertTrue(any(item["is_dummy"] for item in private))
        self.assertNotIn("is_dummy", encoded)

    def test_dynamic_planner_follow_up(self):
        example = run_dynamic_planning_example()
        events = [item["event"] for item in example["transcript"]]
        self.assertEqual(events, ["PROPOSE_ACTION", "SANITIZED_RESULT", "SUBMIT_FOLLOW_UP", "SANITIZED_RESULT"])
        self.assertEqual(example["result"]["effect_count"], 1)
        self.assertEqual(example["transcript"][1]["result"], "CONTINUE")

    def test_l2_public_runtime_existing_approval_path(self):
        python = ROOT / ".venv-stage9" / "Scripts" / "python.exe"
        core = ROOT / "external_stage9" / "agent-framework" / "python" / "packages" / "core"
        self.assertTrue(python.exists())
        self.assertTrue(core.exists())
        env = dict(os.environ)
        env["PYTHONPATH"] = str(core)
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "public_runtime_probe_test.json"
            subprocess.run([str(python), "-m", "stage9_adaptive.public_runtime_probe", "--output", str(output)], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(payload["trajectory_distinguishable"])
        self.assertTrue(payload["same_initial_task"])
        self.assertTrue(payload["same_final_effect"])
        self.assertEqual(payload["semantic_patches"], "none")
        self.assertEqual(payload["existing_rule"]["effect_count"], 1)
        self.assertEqual(payload["missing_rule"]["effect_count"], 1)
        self.assertEqual(len(payload["existing_rule"]["host_visible_trace"]), 1)
        self.assertEqual(len(payload["missing_rule"]["host_visible_trace"]), 2)


if __name__ == "__main__":
    unittest.main()
