from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GROUPS = {
    "TRUSTED_CONTROL_SUBSTRATE": [
        "agent_control_virtualization/ir.py", "agent_control_virtualization/ir_v2.py",
        "agent_control_virtualization/runtime.py", "agent_control_virtualization/runtime_v2.py",
        "privacy_kernel/control.py", "privacy_kernel/protocol.py", "privacy_kernel/lookup.py",
    ],
    "TRUSTED_GATEWAY_ENFORCEMENT": [
        "common_action_gateway_v2/diagnostics.go", "common_action_gateway_v2/mapping_linux.go",
        "common_action_gateway_v2/mapping_windows.go", "common_action_gateway_v2/operation_journal.go",
        "common_action_gateway_v2/pacer.go", "common_action_gateway_v2/platform_linux.go",
        "common_action_gateway_v2/platform_windows.go", "common_action_gateway_v2/profile.go",
        "common_action_gateway_v2/protocol.go", "common_action_gateway_v2/provider.go",
        "common_action_gateway_v2/ring.go", "common_action_gateway_v2/transport.go",
        "common_action_gateway_v2/worker.go", "common_action_gateway_v2/cmd/gateway-pacer/main.go",
        "common_action_gateway_v2/cmd/gateway-worker/main.go",
    ],
    "COMPILER_NOT_RUNTIME_TCB": [
        "agent_control_virtualization/compiler.py", "agent_control_virtualization/compiler_v2.py",
        "canonical_v3/compiler.py",
    ],
    "CORPUS_AND_EXTRACTION_TOOLING": [
        "corpus_audit/extractor.py", "corpus_audit/ir_v1_freeze.py",
        "scripts/audit_workflow_executability_v2.py", "scripts/decompose_mixed_unproven_v2.py",
        "scripts/freeze_semantic_holdout_v2.py",
    ],
    "PROVIDER_EMULATOR_NOT_TCB": [
        "common_action_gateway_v2/provider_emulator.go",
        "common_action_gateway_v2/cmd/local-provider-emulator/main.go",
    ],
    "EXPERIMENTAL_ANALYSIS_NOT_TCB": [
        "canonical_v3/runner.py", "canonical_v3/workflows.py",
        "semantic_fidelity/evaluate.py", "semantic_fidelity/evaluate_v2.py",
        "scripts/run_semantic_holdout_v2_once.py", "scripts/run_long_horizon_structural_v1.py",
    ],
    "UNTRUSTED_CLOUD_PLANE": [
        "cloud_slot_proxy/proxy.py", "common_action_gateway_v2/client.go",
        "common_action_gateway_v2/cmd/gateway-cloud-client/main.go",
    ],
}


def source_lines(path: Path) -> tuple[int, int]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    code = 0
    in_block = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if path.suffix == ".py":
            if stripped.startswith("#"):
                continue
        else:
            if in_block:
                if "*/" in stripped: in_block = False
                continue
            if stripped.startswith("/*"):
                in_block = "*/" not in stripped
                continue
            if stripped.startswith("//"):
                continue
        code += 1
    return len(lines), code


def main() -> None:
    output = ROOT / "TCB_INVENTORY_V4.csv"
    rows = []
    for group, paths in GROUPS.items():
        for relative in paths:
            physical, code = source_lines(ROOT / relative)
            rows.append({"group": group, "path": relative, "physical_loc": physical,
                         "approx_code_loc": code,
                         "runtime_tcb": "YES" if group.startswith("TRUSTED_") else "NO"})
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    for group in GROUPS:
        selected = [row for row in rows if row["group"] == group]
        print(group, len(selected), sum(row["physical_loc"] for row in selected),
              sum(row["approx_code_loc"] for row in selected))


if __name__ == "__main__":
    main()
