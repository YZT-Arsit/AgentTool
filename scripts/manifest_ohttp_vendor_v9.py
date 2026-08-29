from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party" / "ohttp-go"
OUTPUT = ROOT / "OHTTP_VENDOR_PROVENANCE_V9.json"
EXPECTED_COMMIT = "776f22a178b8332f4acacc2919176df8e61046cc"
ARCHIVE_SHA256 = "7b5dcd5af34e5c0ec478841ea3351ff4bcbab5766872d55cbe44fc10fabba827"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    required = ["go.mod", "go.sum", "vendor/modules.txt", "LICENSE.md", "ohttp.go", "bhttp.go"]
    missing = [name for name in required if not (SOURCE / name).is_file()]
    if missing:
        raise SystemExit(f"incomplete OHTTP source tree: {missing}")

    entries = []
    for path in sorted((item for item in SOURCE.rglob("*") if item.is_file()), key=lambda p: p.relative_to(SOURCE).as_posix()):
        entries.append(
            {
                "path": path.relative_to(SOURCE).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    canonical = "".join(
        f"{entry['sha256']} {entry['bytes']} {entry['path']}\n" for entry in entries
    ).encode()

    go_mod = (SOURCE / "go.mod").read_text(encoding="utf-8")
    direct = []
    inside = False
    for line in go_mod.splitlines():
        stripped = line.strip()
        if stripped == "require (":
            inside = True
            continue
        if inside and stripped == ")":
            inside = False
            continue
        if inside and stripped and not stripped.startswith("//"):
            fields = stripped.split()
            if len(fields) >= 2:
                direct.append({"module": fields[0], "version": fields[1]})

    transitive = []
    for line in (SOURCE / "vendor" / "modules.txt").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^# (\S+) (\S+)$", line)
        if match:
            transitive.append({"module": match.group(1), "version": match.group(2)})

    payload = {
        "schema": "AgentTool.OHTTPVendorProvenanceV9/2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SOURCE_AVAILABLE",
        "module": "github.com/chris-wood/ohttp-go",
        "expected_upstream_commit": EXPECTED_COMMIT,
        "provenance_class": "SOURCE_TREE_HASH_ONLY",
        "provenance_note": "The archive was fetched from the official GitHub codeload URL naming the expected commit, but repeated Git object fetches did not complete. The commit is therefore not independently verified from .git metadata.",
        "source_archive_sha256": ARCHIVE_SHA256,
        "source_tree_sha256": hashlib.sha256(canonical).hexdigest(),
        "source_file_count": len(entries),
        "source_total_bytes": sum(entry["bytes"] for entry in entries),
        "license": {"spdx": "MIT", "file": "LICENSE.md"},
        "go_mod_sha256": file_sha256(SOURCE / "go.mod"),
        "go_sum_sha256": file_sha256(SOURCE / "go.sum"),
        "vendor_modules_sha256": file_sha256(SOURCE / "vendor" / "modules.txt"),
        "direct_dependencies": direct,
        "vendored_modules": transitive,
        "source_tree_manifest": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("provenance_class", "source_tree_sha256", "source_file_count", "source_total_bytes")}))


if __name__ == "__main__":
    main()
