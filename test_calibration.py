"""Accuracy measurement: label export, label loading, scoring and the evaluator."""

import csv
import json

import pytest

from src.api.models import ClaimEvidenceCreate, ClaimExtractionRequest, ClaimValidationRequest
from src.research.calibration import export_cases, load_cases, score, write_csv
from src.research.evaluate import evaluate
from src.research.models import EvidenceJudgments
from test_platform import session
from test_research_worker import postgres_dsn, repo  # noqa: F401  (shared fixtures)


def test_exported_rows_round_trip_through_labelling(repo, tmp_path):
    s = session(repo)
    claim = repo.extract_claims(
        s.id, ClaimExtractionRequest(source_text="The method improves accuracy.")
    )[0]
    repo.validate_claim(
        claim.id,
        ClaimValidationRequest(
            evidence=[
                ClaimEvidenceCreate(evidence_text=text, relation="mentions", reviewer_id="tester")
                for text in ("Accuracy rises by 4 points.", "Accuracy rises by 4 points.", "Costs are not reported.")
            ]
        ),
    )
    rows = export_cases(repo, s.id)
    assert [r["passage"] for r in rows] == ["Accuracy rises by 4 points.", "Costs are not reported."]
    assert all(r["claim"] == "The method improves accuracy." and r["expected"] == "" for r in rows)

    path = tmp_path / "labels.csv"
    write_csv(rows, path)
    with path.open(newline="") as handle:
        labelled = list(csv.DictReader(handle))
    labelled[0]["expected"] = "Supports"
    write_csv(labelled, path)
    cases, skipped = load_cases(path)
    assert [c["expected"] for c in cases] == ["supports"] and skipped == 1


def test_labels_must_use_known_relations(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"claim": "c", "passage": "p", "expected": "agrees"}]))
    with pytest.raises(ValueError, match="expected must be one of"):
        load_cases(path)


def test_score_reports_accuracy_confusion_and_false_supports():
    results = [
        {"expected": "supports", "actual": "supports", "correct": True},
        {"expected": "insufficient", "actual": "supports", "correct": False},
        {"expected": "contradicts", "actual": "contradicts", "correct": True},
        {"expected": "contradicts", "actual": "error", "correct": False},
    ]
    report = score(results)
    assert report["accuracy"] == 0.5
    assert report["false_support_rate"] == 0.5
    assert report["confusion"]["insufficient"] == {"supports": 1}
    assert report["per_label"]["contradicts"] == {"cases": 2, "correct": 1}
    assert report["errors"] == 1


async def test_evaluate_scores_the_batched_production_judge():
    class Model:
        model = "fixture"

        async def generate(self, schema, instruction, data):
            assert schema is EvidenceJudgments
            passage = data["passages"][0]["text"]
            relation = "contradicts" if "12%" in passage else "supports"
            return EvidenceJudgments(
                judgments=[{"passage": 1, "relation": relation, "quote": passage, "rationale": "r"}]
            ), {}

    report = await evaluate(
        Model(),
        [
            {"claim": "Mortality fell by 45%.", "passage": "Mortality fell by 12%.", "expected": "contradicts"},
            {"claim": "Mortality fell by 45%.", "passage": "Unrelated text.", "expected": "insufficient"},
        ],
    )
    assert report["total"] == 2 and report["correct"] == 1
    assert report["false_support_rate"] == 1.0
