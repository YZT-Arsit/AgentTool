from __future__ import annotations

import csv
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRUSTED = [
    "action_privacy_v6/bootstrap.py",
    "action_privacy_v6/descriptor.py", "action_privacy_v6/models.py",
    "action_privacy_v6/trusted_module.py", "action_privacy_v6/resolution.py",
]
REUSED_TRUSTED = ["confidential_v5/attestation.py"]


def py_sloc(path: Path) -> int:
    with path.open("rb") as handle:
        tokens = tokenize.tokenize(handle.readline)
        return len({token.start[0] for token in tokens if token.type not in
                    (tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                     tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER)})


def rough_sloc(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("//"))


def main() -> None:
    rows = []
    for relative in TRUSTED:
        rows.append({"component": "TRUSTED_ACTION_MODULE", "path": relative,
                     "code_loc": py_sloc(ROOT / relative), "runtime_tcb": "YES"})
    for relative in REUSED_TRUSTED:
        rows.append({"component": "TRUSTED_ACTION_MODULE", "path": relative,
                     "code_loc": py_sloc(ROOT / relative), "runtime_tcb": "YES_REUSED_BOOTSTRAP"})
    for path in sorted((ROOT / "common_action_gateway_v2").glob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        rows.append({"component": "TRUSTED_GATEWAY", "path": path.relative_to(ROOT).as_posix(),
                     "code_loc": rough_sloc(path), "runtime_tcb": "YES_GATEWAY_DOMAIN"})
    for path in sorted((ROOT / "common_action_gateway_v2" / "cmd").glob("*/*.go")):
        rows.append({"component": "TRUSTED_GATEWAY", "path": path.relative_to(ROOT).as_posix(),
                     "code_loc": rough_sloc(path), "runtime_tcb": "YES_GATEWAY_DOMAIN"})
    with (ROOT / "results_v6" / "tcb_inventory_v6.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary = {}
    for row in rows: summary[row["component"]] = summary.get(row["component"], 0) + row["code_loc"]
    (ROOT / "results_v6" / "tcb_summary_v6.txt").write_text(
        "\n".join(f"{key}={value}" for key, value in summary.items()) + "\n", encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
