from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_control_virtualization.experiment import run


if __name__ == "__main__":
    run(ROOT / "results_control_virtualization")
