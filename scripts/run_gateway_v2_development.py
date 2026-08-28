from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway_v2.development import run_development


if __name__ == "__main__":
    output_name = sys.argv[1] if len(sys.argv) > 1 else "development_stress_windows"
    output = ROOT / "results_gateway_v2" / output_name
    print(json.dumps(run_development(ROOT, output), indent=2))
