from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from canonical_v3.compiler import lower_single_tool_agent
from canonical_v3.runner import run_canonical_gateway
from privacy_kernel.control import ControlKernel
from privacy_kernel.protocol import CanonicalProfile


DEFAULT_OUTPUT = ROOT / "results_canonical_v3" / "real_llm_e2e"


def native_workload() -> FrameworkWorkload:
    from agents import Agent, function_tool

    def local_lookup(topic: str) -> str:
        return f"synthetic:{topic}"

    tool = function_tool(local_lookup, name_override="READ_ONLY_TOOL",
                         description_override="Read one synthetic local record.")
    agent = Agent(
        name="Canonical local-model Agent",
        instructions="Use READ_ONLY_TOOL exactly once and return its synthetic result.",
        tools=[tool],
    )
    return FrameworkWorkload(
        "canonical-real-local-model", "OpenAI Agents SDK",
        "external_stage10/openai-agents-python/examples/basic/tools.py", [agent],
        native_object_types=["agents.agent.Agent", "agents.tool.FunctionTool"],
    )


def profile() -> CanonicalProfile:
    return CanonicalProfile("CANONICAL_V3_REAL_LLM", 1024, 32, 4,
                            100_000_000, 100_000_000, 20_000_000,
                            500_000_000, 100_000_000)


def wait_ready(process: subprocess.Popen[str], timeout: float = 180.0) -> str:
    lines: queue.Queue[str] = queue.Queue()

    def read() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line.rstrip())

    threading.Thread(target=read, daemon=True).start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            error = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"local model server exited before readiness: {error}")
        try:
            line = lines.get(timeout=1)
        except queue.Empty:
            continue
        if line.startswith("READY "):
            return line.split(" ", 1)[1]
    raise TimeoutError("local model server readiness timeout")


def prewarm(endpoint: str) -> dict[str, object]:
    private = {"context": [{"role": "user", "content": "warm up"}], "tools": []}
    request = json.dumps({
        "operation_id": "private-warmup",
        "payload": base64.b64encode(json.dumps(private).encode()).decode("ascii"),
    }).encode("utf-8")
    started = time.perf_counter_ns()
    with urllib.request.urlopen(urllib.request.Request(
            endpoint, data=request, headers={"Content-Type": "application/json"}), timeout=120) as response:
        decoded = json.loads(response.read())
    return {"elapsed_ns": time.perf_counter_ns() - started,
            "status": decoded.get("status"), "payload_present": bool(decoded.get("payload"))}


def command_output(*command: str) -> str:
    try:
        return subprocess.run(command, text=True, capture_output=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def model_file_hashes(model_path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(model_path.glob("*.safetensors")):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        hashes[path.name] = digest.hexdigest()
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--model-python", default=sys.executable)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)
    provider_dir = output / "local_model_provider"
    provider_dir.mkdir()
    process = subprocess.Popen([
        args.model_python, str(ROOT / "scripts/local_openai_gateway_provider.py"),
        "--model-path", str(args.model_path.resolve()), "--revision", args.model_revision,
        "--listen", "127.0.0.1:0", "--private-log", str(provider_dir / "private_model.jsonl"),
        "--metadata", str(provider_dir / "model_metadata.json"),
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        endpoint = wait_ready(process)
        warmup = prewarm(endpoint)
        workload = native_workload()
        compiled = compile_workload_v2(workload, 501, max_model_rounds=2)
        lowered = lower_single_tool_agent(compiled)
        kernel = ControlKernel(lowered.capsules, lowered.initial_agent_id,
                               lowered.provider_by_handle, lowered.tool_name_by_handle,
                               initial_model_input=b"Use the local synthetic lookup Tool and report its result.")
        started = time.perf_counter_ns()
        gateway = run_canonical_gateway(
            ROOT, output / "gateway", profile(), kernel,
            external_provider_endpoints={"LOCAL_MODEL": endpoint}, provider_timeout_ms=30_000,
        )
        elapsed = time.perf_counter_ns() - started
        private_model_rows = [json.loads(line) for line in
                              (provider_dir / "private_model.jsonl").read_text(encoding="utf-8").splitlines()]
        accepted_model_rows = [row for row in private_model_rows
                               if row.get("parse_status") == "ACCEPTED"]
        metadata = json.loads((provider_dir / "model_metadata.json").read_text(encoding="utf-8"))
        result = {
            "status": "PASS" if kernel.state.returned and not kernel.state.failure_class else "FAIL",
            "model": args.model_path.name, "model_revision": args.model_revision,
            "model_weight_sha256": model_file_hashes(args.model_path),
            "model_metadata": metadata, "runtime": {
                "python": platform.python_version(), "platform": platform.platform(),
                "torch": command_output(args.model_python, "-c", "import torch; print(torch.__version__)") ,
                "cuda": command_output(args.model_python, "-c", "import torch; print(torch.version.cuda)"),
                "transformers": command_output(args.model_python, "-c", "import transformers; print(transformers.__version__)"),
                "accelerate": command_output(args.model_python, "-c", "import accelerate; print(accelerate.__version__)"),
                "nvidia_smi": command_output("nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used",
                                             "--format=csv,noheader"),
            },
            "native_framework": workload.framework, "native_source": workload.source,
            "compiler_audit": asdict(compiled.audit), "support_stratum": lowered.support_stratum,
            "openai_compatible_endpoint": endpoint.replace("/execute", "/v1/chat/completions"),
            "gateway_provider_endpoint": endpoint, "prewarm": warmup,
            "gateway_elapsed_ns": elapsed, "gateway": gateway,
            "model_invocations": len(accepted_model_rows) - 1,
            "model_generation_ns": [row["generation_ns"] for row in accepted_model_rows[1:]],
            "model_context": kernel.state.model_context, "tool_results": kernel.state.tool_results,
            "sanitized_final_result": kernel.state.sanitized_result.decode("utf-8"),
            "failure_class": kernel.state.failure_class,
            "dummy_external_effects": 0,
        }
        (output / "real_llm_e2e_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        if result["status"] != "PASS":
            raise SystemExit(1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        if process.stderr:
            (provider_dir / "model_server_stderr.txt").write_text(process.stderr.read(), encoding="utf-8")


if __name__ == "__main__":
    main()
