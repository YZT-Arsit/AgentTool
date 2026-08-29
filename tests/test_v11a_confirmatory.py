from __future__ import annotations

import unittest

from v11_4.profile import selected_profile
from v11a_confirmatory.orchestrator import (
    ExecutionPermit,
    load_semantic_case,
    load_trajectory_case,
    run_native_semantic_case,
)
from v11a_confirmatory.projection import size_projection, structural_prefix, structural_projection


def action(case_id: str = "DEV-V11A-TOOL", framework: str = "OpenAI Agents SDK"):
    return {
        "manifest_kind": "S1_SOURCE_TOOL",
        "case_id": case_id,
        "framework": framework,
        "action_family": "TOOL",
        "logical_action_name": "v11a_dev_tool",
        "argument_schema": {"schema_id": "ONE_STR", "fields": [{"name": "city", "primitive_type": "str"}]},
        "arguments": {"city": "local"},
        "effect_semantics": "READ_ONLY",
        "scenario": "SUCCESS",
        "operation_id": ("op" + case_id.replace("-", ""))[:32],
        "capability": "tool.read",
        "agent_id": 10,
        "agent_capability": "agent.tools",
        "public_profile_id": "V11_4-STRICT-ONLINE-H50-H3000-P10",
    }


class V11AConfirmatoryFreezeTests(unittest.TestCase):
    def test_manifest_loader_is_mechanical_and_native_framework_runs_only_dev(self):
        case = load_semantic_case(action())
        value = run_native_semantic_case(case, ExecutionPermit("V11A_DEVELOPMENT_REGRESSION", True))
        self.assertEqual(value.selected_logical_action, "v11a_dev_tool")
        self.assertTrue(value.final_framework_visible_result_state["action_result_received"])

    def test_selected_execution_requires_v11b(self):
        case = load_semantic_case(action("SELECTED-NOT-DEV"))
        with self.assertRaises(PermissionError):
            run_native_semantic_case(case, ExecutionPermit("V11A_FREEZE", True))

    def test_trajectory_loader_never_executes(self):
        item = action("DEV-V11A-T1")
        item["manifest_kind"] = "S3_CAUSAL_ACTION"
        spec = load_trajectory_case(
            {
                "manifest_kind": "S3_CAUSAL_TRAJECTORY",
                "trajectory_id": "DEV-T",
                "framework": "OpenAI Agents SDK",
                "workflow": "DYNAMIC_SEQUENCE",
                "actions": [item],
            }
        )
        self.assertEqual(len(spec.actions), 1)

    def test_projection_normalizes_authenticated_slot_order_and_excludes_time(self):
        profile = selected_profile(10, 3000)
        base = {
            "profile_id": profile.profile_id,
            "public_relay_events": [],
        }
        for round_number in range(356, 0, -1):
            base["public_relay_events"].append(
                {
                    "profile_id": profile.profile_id,
                    "session": 1,
                    "round": round_number,
                    "request_length": 1079,
                    "response_length": 800,
                    "relay_client_connection_id": "client",
                    "relay_gateway_connection_id": "gateway",
                    "relay_endpoint": "LOCAL_RELAY",
                    "gateway_endpoint": "LOCAL_GATEWAY",
                    "ohttp_key_id": 7,
                    "kem_id": 32,
                    "kdf_id": 1,
                    "aead_id": 1,
                    "config_epoch": 3,
                    "client_http_version": "HTTP/2.0",
                    "gateway_http_version": "HTTP/2.0",
                    "request_observed_ns": round_number,
                    "response_observed_ns": round_number + 1,
                }
            )
        struct = structural_projection(base, profile)
        size = size_projection(base, profile)
        self.assertEqual(struct["round_order"], list(range(1, 357)))
        self.assertNotIn("request_observed_ns", struct)
        self.assertEqual(size["request_final_bytes"], [1079] * 356)
        self.assertEqual(structural_prefix(struct, 10)["round_count"], 10)


if __name__ == "__main__":
    unittest.main()
