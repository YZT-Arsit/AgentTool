from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = "63319014f560f46e2a46dd140f53551e43c27e0d"
FRAMEWORK_SOURCE_DIRS = {
    "OpenAI Agents SDK": ROOT.parent
    / "mediation_trace_validation"
    / "external_stage10"
    / "openai-agents-python",
    "Microsoft Agent Framework": ROOT.parent
    / "mediation_trace_validation"
    / "external_stage9"
    / "agent-framework",
}
BINARIES = {
    "canonical_v4r8_runner": ROOT
    / "common_action_gateway_v2"
    / "bin"
    / "canonical-v12-v4r8-timing-runner",
    "simplepir_v12_timing": ROOT
    / "pir_integration"
    / "simplepir_bridge"
    / "acv-simplepir-v12-timing",
}


def command(*args: str, cwd: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            list(args),
            cwd=cwd or ROOT,
            text=True,
            encoding="utf-8",
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        return f"NOT_AVAILABLE: {type(error).__name__}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_version(*names: str) -> str:
    for name in names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "NOT_AVAILABLE"


def git_source(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"path": str(path), "status": "NOT_AVAILABLE"}
    return {
        "path": str(path),
        "commit": command("git", "rev-parse", "HEAD", cwd=path),
        "status": command("git", "status", "--short", cwd=path),
    }


def optional_text(path: Path) -> str:
    return (
        path.read_text(encoding="utf-8", errors="replace").strip()
        if path.is_file()
        else "NOT_AVAILABLE"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"refusing to overwrite environment snapshot: {args.output}"
        )
    args.output.mkdir(parents=True)
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    pip_freeze = command(sys.executable, "-m", "pip", "freeze")
    (args.output / "FINAL_V4R8_PIP_FREEZE.txt").write_text(
        pip_freeze + "\n", encoding="utf-8", newline="\n"
    )
    cpu_model = "NOT_AVAILABLE"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    mem_total_kib: int | str = "NOT_AVAILABLE"
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("MemTotal:"):
                mem_total_kib = int(line.split()[1])
                break
    os_release = "NOT_AVAILABLE"
    release_path = Path("/etc/os-release")
    if release_path.is_file():
        os_release = release_path.read_text(encoding="utf-8", errors="replace")
    cpu_max = optional_text(Path("/sys/fs/cgroup/cpu.max"))
    cpu_quota_logical: float | str = "NOT_AVAILABLE"
    if cpu_max != "NOT_AVAILABLE" and cpu_max.split()[0] != "max":
        quota, period = (int(value) for value in cpu_max.split())
        cpu_quota_logical = quota / period
    memory_limit = optional_text(Path("/sys/fs/cgroup/memory.max"))
    binaries = {
        name: {
            "path": str(path),
            "byte_size": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else "NOT_AVAILABLE",
        }
        for name, path in BINARIES.items()
    }
    go_binary = ROOT.parent / "go1.26.5" / "bin" / "go"
    go_version = (
        command(str(go_binary), "version")
        if go_binary.is_file()
        else command("go", "version")
    )
    repo = {
        "path": str(ROOT),
        "branch": command("git", "branch", "--show-current"),
        "head": command("git", "rev-parse", "HEAD"),
        "runtime_source_commit": RUNTIME_SOURCE,
        "status": command("git", "status", "--short"),
        "remote_origin": command("git", "remote", "get-url", "origin"),
    }
    snapshot = {
        "schema": "AgentTool.V12V4R8EnvironmentSnapshot/1",
        "host": {
            "hostname": socket.gethostname(),
            "virtualization": command("systemd-detect-virt"),
            "container_cgroup": command("sh", "-c", "cat /proc/1/cgroup"),
            "cpu_model": cpu_model,
            "host_visible_logical_cpu_count": os.cpu_count(),
            "cgroup_cpuset_effective": optional_text(
                Path("/sys/fs/cgroup/cpuset.cpus.effective")
            ),
            "cgroup_cpu_max": cpu_max,
            "cgroup_cpu_quota_logical": cpu_quota_logical,
            "host_visible_ram_total_kib": mem_total_kib,
            "cgroup_memory_max_bytes": memory_limit,
            "filesystem_root": command("df", "-hT", "/root"),
            "filesystem_experiment_source": command("df", "-hT", str(ROOT)),
        },
        "os": {
            "platform": platform.platform(),
            "distribution": os_release,
            "kernel": platform.release(),
            "uname": command("uname", "-a"),
        },
        "languages": {
            "python": sys.version,
            "python_executable": sys.executable,
            "go": go_version,
            "go_executable": str(go_binary)
            if go_binary.is_file()
            else "PATH_RESOLUTION",
        },
        "python_packages": {
            "numpy": package_version("numpy"),
            "scipy": package_version("scipy"),
            "pandas": package_version("pandas"),
            "scikit_learn": package_version("scikit-learn"),
        },
        "frameworks": {
            "OpenAI Agents SDK": {
                "installed_version": package_version("openai-agents"),
                "source": git_source(FRAMEWORK_SOURCE_DIRS["OpenAI Agents SDK"]),
            },
            "Microsoft Agent Framework": {
                "installed_version": package_version(
                    "agent-framework", "agent-framework-core"
                ),
                "source": git_source(
                    FRAMEWORK_SOURCE_DIRS["Microsoft Agent Framework"]
                ),
            },
        },
        "pir": {
            "simplepir_protocol_commit": "e9020b03bf2872c75b8954e749e32408b5db87ed",
            "bridge_source": git_source(ROOT / "pir_integration" / "simplepir_bridge"),
        },
        "repository": repo,
        "binaries": binaries,
        "public_profile": freeze["profile"],
        "environment_variable_names_only": sorted(os.environ),
        "environment_variable_values_recorded": False,
        "secret_values_recorded": False,
    }
    (args.output / "FINAL_V4R8_ENVIRONMENT_SNAPSHOT.json").write_text(
        json.dumps(snapshot, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    system_lines = [
        "V12 V4R8 final execution environment",
        f"hostname: {snapshot['host']['hostname']}",
        f"virtualization: {snapshot['host']['virtualization']}",
        f"cpu: {cpu_model}",
        f"host-visible logical CPUs: {os.cpu_count()}",
        f"cgroup CPU quota: {cpu_quota_logical} logical CPUs ({cpu_max})",
        f"host-visible RAM KiB: {mem_total_kib}",
        f"cgroup memory limit bytes: {memory_limit}",
        f"platform: {snapshot['os']['platform']}",
        f"kernel: {snapshot['os']['kernel']}",
        f"Python: {sys.version}",
        f"Go: {snapshot['languages']['go']}",
        f"execution repository HEAD: {repo['head']}",
        f"V4R8 runtime source: {RUNTIME_SOURCE}",
        f"canonical runner SHA256: {binaries['canonical_v4r8_runner']['sha256']}",
        f"SimplePIR runner SHA256: {binaries['simplepir_v12_timing']['sha256']}",
        "Environment variable values were not recorded.",
    ]
    (args.output / "FINAL_V4R8_SYSTEM_INFO.txt").write_text(
        "\n".join(system_lines) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"snapshot": str(args.output), "head": repo["head"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
