from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _process_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return rows
    for item in proc.iterdir():
        if not item.name.isdigit():
            continue
        try:
            status = {}
            for line in (item / "status").read_text().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    status[key] = value.strip()
            command = (item / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            try:
                executable = Path(os.readlink(item / "exe")).name
            except OSError:
                executable = ""
            rows.append(
                {
                    "pid": int(item.name),
                    "ppid": int(status.get("PPid", "-1")),
                    "state": status.get("State", ""),
                    "command": command,
                    "executable": executable,
                }
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return rows


def snapshot() -> dict[str, Any]:
    pid = os.getpid()
    fd_root = Path("/proc/self/fd")
    descriptors: list[str] = []
    if fd_root.is_dir():
        for item in fd_root.iterdir():
            try:
                descriptors.append(os.readlink(item))
            except OSError:
                pass
    processes = _process_rows()
    children = [item for item in processes if item["ppid"] == pid]
    relevant = [
        item
        for item in processes
        if item["executable"] in {"acv-simplepir-online", "canonical-v11_4-runner"}
    ]
    return {
        "pid": pid,
        "open_fd_count": len(descriptors),
        "open_socket_fds": sum(value.startswith("socket:") for value in descriptors),
        "open_pipe_fds": sum(value.startswith("pipe:") for value in descriptors),
        "live_child_processes": len(children),
        "zombie_children": sum("Z" in item["state"] for item in children),
        "simplepir_processes": sum(item["executable"] == "acv-simplepir-online" for item in relevant),
        "canonical_runner_processes": sum(item["executable"] == "canonical-v11_4-runner" for item in relevant),
        "relevant_processes": relevant,
    }
