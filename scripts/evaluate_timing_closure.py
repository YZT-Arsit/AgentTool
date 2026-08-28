from pathlib import Path

from timing_closure.evaluate import evaluate


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    evaluate(root, root / "results_timing_closure")
