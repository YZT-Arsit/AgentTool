from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timing_closure.interrupted_analysis import run_interrupted_analysis


def main() -> None:
    pir, tool = run_interrupted_analysis(ROOT)
    print(json.dumps({"pir_rows": len(pir), "tool_rows": len(tool)}, indent=2))


if __name__ == "__main__":
    main()

