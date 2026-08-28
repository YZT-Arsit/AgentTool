from __future__ import annotations

import json
from pathlib import Path

from corpus_audit.ir_v1_freeze import generate_ir_v1_freeze


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    print(json.dumps(generate_ir_v1_freeze(ROOT), indent=2))
