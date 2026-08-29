from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_4.profile import selected_profile
from v11a_confirmatory.projection import (
    CONNECTION_HOPS,
    PER_ROUND_SEQUENCE_FIELDS,
    PREFIX_ROUNDS,
    structural_prefix,
    structural_projection,
)


SELECTION_COMMIT = "1c54e9fff88d8751d3a2fe4ed042fce736b71034"
FINAL_FREEZE = "V11A_FINAL_CONFIRMATORY_FREEZE.json"
PROJECTION = "v11a_confirmatory/projection.py"
CANONICAL_PROJECTION = "canonical_v9_1/projection.py"
SEEDS = "V11A_SELECTION_SEEDS.json"
ORDER = "V11A_EXECUTION_ORDER.json"
SELECTED_MANIFESTS = (
    "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json",
    "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json",
    "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json",
    "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json",
    "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json",
)
CANDIDATE_UNIVERSES = (
    "V11A_CANDIDATE_UNIVERSES_FREEZE.json",
    "V11A_SOURCE_TOOL_UNIVERSE.json",
    "V11A_COMPOSITION_UNIVERSE.json",
    "V11A_CAUSAL_TRAJECTORY_UNIVERSE.json",
    "V11A_EFFECT_CONTRACT_UNIVERSE.json",
    "V11A_STRUCTURAL_PAIR_UNIVERSE.json",
)
PAIR_PATHS = {
    "AGENT_IDENTITY": "post_gate_repair_raw/agent_identity_v2",
    "TOOL_ROUTE": "structural_raw/tool_route",
    "ACTION_KIND": "structural_raw/action_kind",
    "ACTION_COUNT": "structural_raw/action_count",
    "REPETITION": "structural_raw/repetition",
    "FREQUENCY": "structural_raw/frequency",
    "RARE_TARGET": "structural_raw/rare_target",
    "TRANSITION_PATTERN": "structural_raw/transition_pattern",
    "ARGUMENT_LENGTH": "structural_raw/argument_length",
    "PROVIDER_READINESS": "structural_raw/provider_readiness",
    "INTERNAL_EXTERNAL": "structural_raw/internal_external",
    "CAUSAL_DEPTH": "structural_raw/causal_depth",
}
RAW_ROOT = ROOT / "tmp" / "v11_4_1_projection_raw" / "results_v11_4_development"
OUTPUTS = {
    "diff": ROOT / "V11A_1_PREFIX_PROJECTION_DIFF.md",
    "tests": ROOT / "V11A_1_PREFIX_PROJECTION_TESTS.md",
    "alignment": ROOT / "V11A_1_PREFIX_PROJECTION_ALIGNMENT.json",
    "freeze": ROOT / "V11A_1_CONFIRMATORY_ANALYSIS_FREEZE.json",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path | str) -> str:
    path = ROOT / path if isinstance(path, str) else path
    return sha256_bytes(path.read_bytes())


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def git_bytes(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{SELECTION_COMMIT}:{path}"], cwd=ROOT)


def unchanged_hash(path: str) -> dict[str, Any]:
    accepted = sha256_bytes(git_bytes(path))
    current = sha256(path)
    diff = subprocess.run(
        ["git", "diff", "--quiet", SELECTION_COMMIT, "--", path],
        cwd=ROOT,
        capture_output=True,
    )
    return {
        "accepted_commit_blob_sha256": accepted,
        "current_checkout_exact_sha256": current,
        "git_projection_unchanged": diff.returncode == 0,
        "unchanged": diff.returncode == 0,
    }


def function_ast_hash(source: bytes, name: str) -> str:
    tree = ast.parse(source.decode("utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return sha256_bytes(ast.dump(node, include_attributes=False).encode())
    raise KeyError(name)


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", errors="strict")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prefix_gate(full: dict[str, Any], horizon: int) -> dict[str, Any]:
    prefix = structural_prefix(full, horizon)
    lengths = {field: len(prefix[field]) for field in PER_ROUND_SEQUENCE_FIELDS}
    connection_lengths = {
        hop: len(prefix["connection_reuse_pattern"][hop]) for hop in CONNECTION_HOPS
    }
    connection_counts = {
        hop: prefix["connection_count"][hop] for hop in CONNECTION_HOPS
    }
    recomputed_counts = {
        hop: len(set(prefix["connection_reuse_pattern"][hop])) for hop in CONNECTION_HOPS
    }
    return {
        "projection": prefix,
        "all_per_round_lengths_equal_h": all(value == horizon for value in lengths.values()),
        "connection_lengths_equal_h": all(value == horizon for value in connection_lengths.values()),
        "connection_counts_recomputed": connection_counts == recomputed_counts,
        "round_count_equal_h": prefix["round_count"] == horizon,
        "public_scalars_unchanged": all(
            prefix[field] == full[field]
            for field in ("session_count", "connection_policy", "scheduled_public_lifetime_ns")
        ),
    }


def existing_development_recompute() -> dict[str, Any]:
    if not RAW_ROOT.is_dir():
        raise FileNotFoundError("immutable V11.4 raw trace archive is unavailable")
    profile = selected_profile(10, 3000)
    pair_rows = []
    all_arm_gates = []
    for pair, relative in PAIR_PATHS.items():
        arm_prefixes: dict[str, dict[int, dict[str, Any]]] = {}
        arm_hashes: dict[str, str] = {}
        full_values: dict[str, dict[str, Any]] = {}
        for arm in ("A", "B"):
            path = RAW_ROOT / relative / arm / "go_online_result.json"
            trace = json.loads(path.read_text(encoding="utf-8"))
            full = structural_projection(trace, profile)
            full_values[arm] = full
            arm_hashes[arm] = sha256(path)
            arm_prefixes[arm] = {}
            for horizon in PREFIX_ROUNDS:
                gate = prefix_gate(full, horizon)
                all_arm_gates.append(gate)
                arm_prefixes[arm][horizon] = gate["projection"]
            if arm_prefixes[arm][356] != full:
                raise AssertionError(f"{pair}/{arm} full-horizon prefix differs from full projection")
        equal_horizons = [
            horizon
            for horizon in PREFIX_ROUNDS
            if arm_prefixes["A"][horizon] == arm_prefixes["B"][horizon]
        ]
        pair_rows.append(
            {
                "pair": pair,
                "raw_trace_sha256": arm_hashes,
                "equal_prefix_horizons": equal_horizons,
                "all_seven_prefixes_equal": equal_horizons == list(PREFIX_ROUNDS),
                "full_projection_equal": full_values["A"] == full_values["B"],
            }
        )
    return {
        "source": "existing immutable V11.4 development raw traces; no workload rerun",
        "pairs": pair_rows,
        "pair_count": len(pair_rows),
        "all_pairs_all_prefixes_equal": all(row["all_seven_prefixes_equal"] for row in pair_rows),
        "full_projection_pairs_equal": all(row["full_projection_equal"] for row in pair_rows),
        "prefix_length_invariant": all(
            row["all_per_round_lengths_equal_h"] and row["connection_lengths_equal_h"]
            for row in all_arm_gates
        ),
        "prefix_connection_count_recomputed": all(
            row["connection_counts_recomputed"] for row in all_arm_gates
        ),
        "public_scalars_unchanged": all(row["public_scalars_unchanged"] for row in all_arm_gates),
        "prefix_356_equals_full": True,
    }


def main() -> None:
    if any(path.exists() for path in OUTPUTS.values()):
        raise FileExistsError("refusing to overwrite V11A.1 analysis freeze artifacts")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != SELECTION_COMMIT:
        raise RuntimeError("V11A.1 requires the accepted V11A selection commit")

    final_freeze_check = unchanged_hash(FINAL_FREEZE)
    selected_checks = {path: unchanged_hash(path) for path in SELECTED_MANIFESTS}
    universe_checks = {path: unchanged_hash(path) for path in CANDIDATE_UNIVERSES}
    seed_check = unchanged_hash(SEEDS)
    order_check = unchanged_hash(ORDER)
    canonical_projection_check = unchanged_hash(CANONICAL_PROJECTION)
    prior_final = json.loads((ROOT / FINAL_FREEZE).read_text(encoding="utf-8"))
    prior_bound_hashes = prior_final["bound_files"]
    prior_bound_files_match = all(
        sha256(path) == prior_bound_hashes[path]
        for path in (*SELECTED_MANIFESTS, SEEDS, ORDER, CANONICAL_PROJECTION)
    )
    if not all(
        [
            final_freeze_check["unchanged"],
            seed_check["unchanged"],
            order_check["unchanged"],
            canonical_projection_check["unchanged"],
            prior_bound_files_match,
            *(value["unchanged"] for value in selected_checks.values()),
            *(value["unchanged"] for value in universe_checks.values()),
        ]
    ):
        raise RuntimeError("V11A selection or frozen candidate material changed")

    old_projection = git_bytes(PROJECTION)
    current_projection = (ROOT / PROJECTION).read_bytes()
    wrapper_functions = ("authenticated_slot_order", "structural_projection", "size_projection")
    wrapper_checks = {
        name: {
            "old_ast_sha256": function_ast_hash(old_projection, name),
            "current_ast_sha256": function_ast_hash(current_projection, name),
        }
        for name in wrapper_functions
    }
    full_wrapper_unchanged = all(
        value["old_ast_sha256"] == value["current_ast_sha256"]
        for value in wrapper_checks.values()
    )
    if not full_wrapper_unchanged:
        raise RuntimeError("full structural or size wrapper semantics changed")

    test_command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_v11a_1_prefix_projection.py",
        "-v",
    ]
    completed = subprocess.run(test_command, cwd=ROOT, text=True, capture_output=True)
    test_output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        raise RuntimeError(test_output)

    development = existing_development_recompute()
    if not all(
        development[key]
        for key in (
            "all_pairs_all_prefixes_equal",
            "full_projection_pairs_equal",
            "prefix_length_invariant",
            "prefix_connection_count_recomputed",
            "public_scalars_unchanged",
            "prefix_356_equals_full",
        )
    ):
        raise AssertionError("corrected-prefix development recomputation failed")

    final_frozen = json.loads((ROOT / FINAL_FREEZE).read_text(encoding="utf-8"))
    selected_executed = int(final_frozen["selected_holdout_cases_executed"])
    if selected_executed != 0 or (ROOT / "results_v11b_confirmatory").exists():
        raise RuntimeError("selected holdout execution evidence exists")

    alignment = {
        "schema": "AgentTool.V11A_1PrefixProjectionAlignment/1",
        "phase": "ANALYSIS_ONLY_NO_SELECTED_EXECUTION",
        "v11a_selection_commit": SELECTION_COMMIT,
        "v11a_final_confirmatory_freeze": final_freeze_check,
        "prior_v11a_bound_file_hashes_match_current_checkout": prior_bound_files_match,
        "old_frozen_v11a_projection_sha256": sha256_bytes(old_projection),
        "corrected_v11a_projection_sha256": sha256_bytes(current_projection),
        "canonical_full_projection": canonical_projection_check,
        "full_structural_and_size_wrappers": wrapper_checks,
        "full_structural_projection_changed": not full_wrapper_unchanged,
        "size_projection_changed": not full_wrapper_unchanged,
        "selected_manifest_hashes": selected_checks,
        "candidate_universe_hashes": universe_checks,
        "selection_seed": seed_check,
        "execution_order": order_check,
        "no_reselection": True,
        "no_seed_derivation": True,
        "no_candidate_universe_change": True,
        "selected_holdout_cases_executed": selected_executed,
        "prefix_horizons": list(PREFIX_ROUNDS),
        "per_round_sequence_fields": list(PER_ROUND_SEQUENCE_FIELDS),
        "connection_hops": list(CONNECTION_HOPS),
        "synthetic_test": {
            "command": test_command,
            "result": "3/3 PASS",
            "output_sha256": sha256_bytes(test_output.encode()),
        },
        "existing_development_recompute": development,
        "true_prefix_projection": "PASS",
        "prefix_length_invariant": "PASS",
        "prefix_connection_count_recomputed": "PASS",
    }
    write_json(OUTPUTS["alignment"], alignment)

    write_text(
        OUTPUTS["diff"],
        "# V11A.1 prefix-projection difference\n\n"
        "The accepted V11A full structural and size projections are unchanged. The old `structural_prefix()` truncated only endpoint, session, round, HTTP-version, and length sequences while retaining full-session cryptographic/configuration sequences and connection metadata.\n\n"
        "The corrected function truncates all 15 per-round sequences, truncates both nested connection-reuse sequences, recomputes each prefix-local connection count from aliases visible by that horizon, preserves only public session/profile scalars, and sets `round_count = h`. `prefix(356)` is byte-for-value equal to the full structural projection. No timestamp is added.\n\n"
        "No selected manifest, seed, execution order, candidate universe, V11.4 runtime component, canonical full projection, or size projection changed.\n",
    )
    write_text(
        OUTPUTS["tests"],
        "# V11A.1 prefix-projection tests\n\n"
        "- Synthetic non-holdout unit tests: **3/3 PASS**.\n"
        "- Reconnect fixture: prefixes 50 and 100 see one connection; prefix 200 sees two.\n"
        "- A controlled public difference after round 150 is absent at prefix 100 and present at prefix 200.\n"
        f"- Every per-round and nested connection sequence has length `h` at {list(PREFIX_ROUNDS)}.\n"
        "- `prefix(356) == full projection`: **PASS**.\n"
        "- Existing immutable V11.4 development traces: **12/12 pairs**, all seven corrected prefixes equal; no workload rerun.\n"
        "- Selected V11A executions: **0**.\n\n"
        f"Test-output SHA-256: `{alignment['synthetic_test']['output_sha256']}`.\n",
    )

    freeze = {
        "schema": "AgentTool.V11A_1ConfirmatoryAnalysisFreeze/1",
        "status": "FROZEN_ANALYSIS_ONLY_NO_SELECTED_EXECUTION",
        "v11a_selection_commit": SELECTION_COMMIT,
        "v11a_final_confirmatory_freeze_sha256": sha256(FINAL_FREEZE),
        "old_frozen_v11a_projection_sha256": sha256_bytes(old_projection),
        "corrected_v11a_projection_sha256": sha256(PROJECTION),
        "unchanged_selected_manifest_hashes": {
            path: value["current_checkout_exact_sha256"] for path, value in selected_checks.items()
        },
        "unchanged_candidate_universe_hashes": {
            path: value["current_checkout_exact_sha256"] for path, value in universe_checks.items()
        },
        "unchanged_execution_order_sha256": order_check["current_checkout_exact_sha256"],
        "unchanged_selection_seed_sha256": seed_check["current_checkout_exact_sha256"],
        "unchanged_canonical_full_projection_sha256": canonical_projection_check["current_checkout_exact_sha256"],
        "corrected_prefix_test_result": "3/3 PASS",
        "development_prefix_recompute": "12/12 PAIRS; 84/84 PREFIX COMPARISONS PASS",
        "bound_analysis_files": {
            PROJECTION: sha256(PROJECTION),
            "tests/test_v11a_1_prefix_projection.py": sha256("tests/test_v11a_1_prefix_projection.py"),
            "scripts/freeze_v11a_1_prefix_alignment.py": sha256(
                "scripts/freeze_v11a_1_prefix_alignment.py"
            ),
            OUTPUTS["diff"].name: sha256(OUTPUTS["diff"]),
            OUTPUTS["tests"].name: sha256(OUTPUTS["tests"]),
            OUTPUTS["alignment"].name: sha256(OUTPUTS["alignment"]),
        },
        "selected_cases_changed": False,
        "seeds_changed": False,
        "execution_order_changed": False,
        "full_structural_projection_changed": False,
        "size_projection_changed": False,
        "selected_holdout_cases_executed": 0,
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
        "ready_for_v11b_independent_audit": "YES",
    }
    freeze["aggregate_sha256"] = canonical_sha(freeze)
    write_json(OUTPUTS["freeze"], freeze)
    print("TRUE_PREFIX_PROJECTION=PASS")
    print("DEVELOPMENT_PREFIX_RECOMPUTE=12/12;84/84")
    print("SELECTED_HOLDOUT_CASES_EXECUTED=0")


if __name__ == "__main__":
    main()
