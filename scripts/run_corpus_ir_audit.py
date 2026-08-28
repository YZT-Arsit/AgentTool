from __future__ import annotations

import json
from pathlib import Path

from corpus_audit.extractor import run_corpus_audit
from corpus_audit.ir_v1_freeze import verify_frozen_baseline


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    if (ROOT / "IR_V1_BASELINE_MANIFEST.json").exists():
        verify_frozen_baseline(ROOT)
        raise SystemExit(
            "IR-v1 is permanently frozen. This command will not overwrite its artifacts. "
            "Implement IR-v2 as a new version and evaluate it on the frozen corpus membership."
        )
    print(json.dumps(run_corpus_audit(ROOT), indent=2))
