from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "STRUCTURAL_SIZE_HOLDOUT_V7_FREEZE.json"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"holdout already frozen: {OUTPUT}")
    n = 50
    alternating = lambda a, b: [a if index % 2 == 0 else b for index in range(n)]
    manifest = {
        "holdout_id": "STRICT-STRUCTURAL-SIZE-V7-20260828",
        "status": "FROZEN_AFTER_DEVELOPMENT_BEFORE_EXECUTION",
        "public_profile": {
            "name": "V7-STRICT-HOLDOUT-STANDARD",
            "real_operations": n,
            "frame_bytes": 1024,
            "request_delta_ns": 2_000_000,
            "response_delta_ns": 10_000_000,
            "mask_ns": 2_000_000,
            "provider_completion_bound_ns": 800_000_000,
        },
        "observer_projection": ["direction", "session", "slot", "frame_bytes", "destination"],
        "timing_features_excluded": True,
        "windows": [1, 5, 10, 25, 50],
        "run_rule": "execute once on authorized Linux host; no tuning/replacement",
        "pairs": [
            {"pair_id": "TOOL_TARGET", "secret": "provider target", "a": ["FAST"] * n, "b": ["MEDIUM"] * n},
            {"pair_id": "REPEATED_TARGET", "secret": "same target versus varied targets", "a": ["FAST"] * n,
             "b": ["FAST", "MEDIUM", "SLOW", "JITTERED"] * 12 + ["FAST", "MEDIUM"]},
            {"pair_id": "FREQUENCY", "secret": "target frequency", "a": ["FAST"] * 45 + ["MEDIUM"] * 5,
             "b": ["MEDIUM"] * 45 + ["FAST"] * 5},
            {"pair_id": "RARE_TARGET", "secret": "single rare target occurrence", "a": ["FAST"] * n,
             "b": ["FAST"] * 37 + ["JITTERED"] + ["FAST"] * 12},
            {"pair_id": "TRANSITION_PATTERN", "secret": "alternating target transition", "a": alternating("FAST", "MEDIUM"),
             "b": alternating("FAST", "SLOW")},
            {"pair_id": "CROSS_SESSION_LINK", "secret": "same versus different target across independent public sessions",
             "a": ["SLOW"] * n, "b": ["JITTERED"] * n},
        ],
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    (ROOT / "STRUCTURAL_SIZE_HOLDOUT_V7_FREEZE_SHA256.txt").write_text(digest + "\n", encoding="utf-8")
    print(digest)


if __name__ == "__main__":
    main()
