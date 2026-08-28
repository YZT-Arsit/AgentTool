from __future__ import annotations

import json
from pathlib import Path

from corpus_audit.extractor import run_corpus_audit


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    print(json.dumps(run_corpus_audit(ROOT), indent=2))

