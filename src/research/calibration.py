"""Measure claim-check accuracy against labels from a real research field.

1. Export claims with their stored evidence passages from one of your sessions:

       uv run python -m src.research.calibration export SESSION_ID --out labels.csv

2. Open labels.csv and fill the ``expected`` column for each row with
   ``supports``, ``contradicts`` or ``insufficient``, judging only the passage.
   Leave rows blank to skip them.

3. Score the configured model against your labels (one model call per row):

       uv run python -m src.research.evaluate --cases labels.csv --out report.json

The report's ``false_support_rate`` is the share of "supports" verdicts that your
labels say were wrong — the error that matters most, because it promotes claims.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

RELATIONS = ("supports", "contradicts", "insufficient")
FIELDS = ["id", "claim", "passage", "paper", "page", "expected", "note"]


def load_cases(path: str | Path) -> tuple[list[dict], int]:
    """Labelled cases from JSON or CSV, and how many unlabelled rows were skipped."""

    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
    cases, skipped = [], 0
    for number, row in enumerate(rows, 1):
        expected = (row.get("expected") or "").strip().lower()
        if not expected:
            skipped += 1
            continue
        if expected not in RELATIONS:
            raise ValueError(
                f"Row {number}: expected must be one of {', '.join(RELATIONS)}, not {expected!r}"
            )
        if not (row.get("claim") or "").strip() or not (row.get("passage") or "").strip():
            raise ValueError(f"Row {number}: claim and passage are required")
        cases.append({**row, "expected": expected})
    return cases, skipped


def score(results: list[dict]) -> dict:
    """Accuracy, per-label results, confusion counts and the false-support rate."""

    confusion: dict[str, Counter] = {label: Counter() for label in RELATIONS}
    for item in results:
        confusion[item["expected"]][item["actual"]] += 1
    said_supports = sum(row["supports"] for row in confusion.values())
    wrong_supports = said_supports - confusion["supports"]["supports"]
    correct = sum(item["correct"] for item in results)
    return {
        "total": len(results),
        "correct": correct,
        "accuracy": round(correct / len(results), 3) if results else None,
        "per_label": {
            label: {
                "cases": sum(confusion[label].values()),
                "correct": confusion[label][label],
            }
            for label in RELATIONS
        },
        "confusion": {label: dict(confusion[label]) for label in RELATIONS},
        "false_support_rate": round(wrong_supports / said_supports, 3)
        if said_supports
        else None,
        "errors": sum(item["actual"] == "error" for item in results),
    }


def export_cases(repository, session_id: str, *, limit: int = 200) -> list[dict]:
    """One row per claim and stored evidence passage, ready to label."""

    papers = {p.paper.id: p.paper for p in repository.list_papers(session_id)}
    rows, seen = [], set()
    for claim in repository.list_claims(session_id):
        if claim.status.value == "speculative":
            continue
        for evidence in repository.list_claim_evidence(claim.id):
            key = (claim.id, evidence.evidence_text)
            if key in seen:
                continue
            seen.add(key)
            paper = papers.get(evidence.paper_id)
            rows.append(
                {
                    "id": f"{claim.id}:{evidence.id}",
                    "claim": claim.claim_text,
                    "passage": evidence.evidence_text,
                    "paper": paper.title if paper else "",
                    "page": evidence.page_start or "",
                    "expected": "",
                    "note": "",
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def write_csv(rows: list[dict], path: str | Path) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    from dotenv import load_dotenv

    from ..api.repository_factory import create_repository

    load_dotenv()
    parser = argparse.ArgumentParser(description="Export claim-check cases to label")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Write a session's claims and passages as CSV")
    export.add_argument("session_id")
    export.add_argument("--out", default="labels.csv")
    export.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    repository = create_repository()
    try:
        rows = export_cases(repository, args.session_id, limit=args.limit)
    finally:
        if hasattr(repository, "close"):
            repository.close()
    write_csv(rows, args.out)
    print(f"Wrote {len(rows)} rows to {args.out}. Fill the expected column, then run src.research.evaluate.")


if __name__ == "__main__":
    main()
