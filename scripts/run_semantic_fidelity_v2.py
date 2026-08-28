from __future__ import annotations

import asyncio
import argparse
import json
from pathlib import Path

from semantic_fidelity.evaluate_v2 import run_frozen_72_v2


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_frozen_72_v2(ROOT, args.output)), indent=2))
