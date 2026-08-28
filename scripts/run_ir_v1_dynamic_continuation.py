from __future__ import annotations

import asyncio
import json
from pathlib import Path

from semantic_fidelity.evaluate import run_ir_v1_dynamic_continuation


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_ir_v1_dynamic_continuation(ROOT)), indent=2))
