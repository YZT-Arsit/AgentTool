from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "TCB_INVENTORY_V5.csv"

GROUPS = {
    "TEE_CONTROL_RUNTIME": [
        "confidential_v5/attestation.py", "confidential_v5/profiles.py",
        "confidential_v5/membership.py", "confidential_v5/resolution.py",
        "confidential_v5/verifier.py", "confidential_v5/kernel.py",
        "agent_control_virtualization/ir.py", "privacy_kernel/control.py",
        "privacy_kernel/protocol.py", "privacy_kernel/lookup.py",
    ],
    "TEE_REFERENCE_SEMANTIC_RUNTIME": [
        "agent_control_virtualization/ir_v2.py", "agent_control_virtualization/runtime_v2.py",
    ],
    "TRUSTED_GATEWAY_OUTSIDE_TEE_OR_SEPARATE_CVM": [
        "common_action_gateway_v2/diagnostics.go", "common_action_gateway_v2/mapping_linux.go",
        "common_action_gateway_v2/mapping_windows.go", "common_action_gateway_v2/operation_journal.go",
        "common_action_gateway_v2/pacer.go", "common_action_gateway_v2/platform_linux.go",
        "common_action_gateway_v2/platform_windows.go", "common_action_gateway_v2/profile.go",
        "common_action_gateway_v2/protocol.go", "common_action_gateway_v2/provider.go",
        "common_action_gateway_v2/ring.go", "common_action_gateway_v2/transport.go",
        "common_action_gateway_v2/worker.go", "common_action_gateway_v2/cmd/gateway-pacer/main.go",
        "common_action_gateway_v2/cmd/gateway-worker/main.go",
    ],
    "COMPILER_CLASSIFIER_NOT_RUNTIME_TCB": [
        "agent_control_virtualization/compiler.py", "agent_control_virtualization/compiler_v2.py",
        "canonical_v3/compiler.py", "semantic_fidelity/harness_v3.py",
        "scripts/run_v5_offline_classifier.py",
    ],
}


def counts(path: Path) -> tuple[int, int]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    code = sum(bool(line.strip()) and not line.lstrip().startswith(("#", "//")) for line in lines)
    return len(lines), code


def framework_count(root: Path) -> tuple[int, int, int]:
    files = list(root.rglob("*.py"))
    values = [counts(path) for path in files]
    return len(files), sum(v[0] for v in values), sum(v[1] for v in values)


def main() -> None:
    rows = []
    for group, paths in GROUPS.items():
        for relative in paths:
            physical, code = counts(ROOT / relative)
            rows.append({"group": group, "path": relative, "files": 1,
                         "physical_loc": physical, "approx_code_loc": code,
                         "inside_tee": "YES" if group.startswith("TEE_") else "NO",
                         "runtime_tcb": "YES" if group != "COMPILER_CLASSIFIER_NOT_RUNTIME_TCB" else "NO"})
    baselines = (
        ("FULL_TRUSTED_RUNTIME_OPENAI", ROOT / "external_stage10/openai-agents-python/src/agents"),
        ("FULL_TRUSTED_RUNTIME_MICROSOFT", ROOT / "external_stage9/agent-framework/python/packages/core/agent_framework"),
    )
    for group, path in baselines:
        files, physical, code = framework_count(path)
        rows.append({"group": group, "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                     "files": files, "physical_loc": physical, "approx_code_loc": code,
                     "inside_tee": "BASELINE", "runtime_tcb": "BASELINE"})
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = {}
    for group in GROUPS | dict(baselines):
        selected = [r for r in rows if r["group"] == group]
        summary[group] = {"files": sum(int(r["files"]) for r in selected),
                          "physical_loc": sum(int(r["physical_loc"]) for r in selected),
                          "approx_code_loc": sum(int(r["approx_code_loc"]) for r in selected)}
    (ROOT / "results_v5").mkdir(exist_ok=True)
    (ROOT / "results_v5/tcb_v5_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
