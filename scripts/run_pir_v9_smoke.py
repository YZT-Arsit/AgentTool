from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from action_privacy_v8.descriptor import AgentDescriptorV7Codec
from cryptographic_closure.pir_backend import PIRRequest, read_raw_queries, run_simplepir
from scripts.run_pir_v7_descriptor_v8 import EPOCH, build_registry, descriptor


def main() -> None:
    output = ROOT / "results_v9" / "pir_v7_descriptor_smoke"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="agenttool-v9-pir-", dir=output.parent))
    try:
        codec = AgentDescriptorV7Codec(os.urandom(32), EPOCH)
        registry = scratch / "encrypted_agent_descriptor_v7_rows.bin"
        build_registry(registry, 1_000, codec)
        indices = (0, 499, 499, 999)
        requests = [
            PIRRequest("v9-post-ohttp-smoke", ordinal, index, "PRIVATE_SELECTION")
            for ordinal, index in enumerate(indices)
        ]
        artifacts = run_simplepir(ROOT, registry, 1_000, requests, scratch / "simplepir")
        recovered = [
            codec.decode(row, expected_agent_id=index)
            for row, index in zip(artifacts.recovered, indices, strict=True)
        ]
        if any(value != descriptor(index) for value, index in zip(recovered, indices, strict=True)):
            raise AssertionError("post-OHTTP PIR smoke recovered the wrong AgentDescriptorV7")
        raw = read_raw_queries(artifacts.raw_query_path)
        if hashlib.sha256(raw[1]).digest() == hashlib.sha256(raw[2]).digest():
            raise AssertionError("repeated PIR query did not use fresh query bytes")
        shutil.move(str(scratch), str(output))
        print(f"PASS: {len(indices)}/{len(indices)} authenticated descriptors; output={output}")
    except Exception:
        shutil.rmtree(scratch, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
