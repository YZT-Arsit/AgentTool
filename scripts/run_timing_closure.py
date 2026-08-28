from pathlib import Path

from timing_closure.runner import run_all


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    run_all(root, root / "results_timing_closure")
