from __future__ import annotations

import asyncio
import json
from pathlib import Path

from semantic_fidelity.evaluate_v2 import run_frozen_72_v2


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_frozen_72_v2(ROOT)), indent=2))
