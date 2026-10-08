"""Score claim checks against labelled cases: the synthetic regression set or your own field's labels."""

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from ..claims import EvidenceCandidate, EvidenceRetriever
from ..claims.semantic_verifier import judge_passages
from .calibration import load_cases, score
from .model import ResearchModel


async def evaluate(model, cases):
    results = []
    for case in cases:
        candidates = EvidenceRetriever().retrieve(
            case["claim"],
            [
                EvidenceCandidate(
                    source_type="paper_abstract",
                    paper_id="synthetic-eval",
                    evidence_text=case["passage"],
                )
            ],
            min_score=0,
        )
        try:
            # The production path judges every retrieved passage in one batched call.
            [(evidence, _)] = await judge_passages(case["claim"], candidates[:1], model)
            actual = evidence.relation.value
            # An unjudged passage means the model gave no usable answer for it.
            actual, error = ("error", "unjudged") if actual == "mentions" else (actual, None)
        except Exception as exc:
            actual, error = "error", type(exc).__name__
        results.append(
            {
                **case,
                "actual": actual,
                "correct": actual == case["expected"],
                "error": error,
            }
        )
    return {
        "model": model.model,
        **score(results),
        "note": "Accuracy on these cases only; a small or synthetic set is not a calibrated benchmark.",
        "results": results,
    }


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Score claim checks against labelled cases")
    parser.add_argument(
        "--cases",
        help="Labelled JSON or CSV (see src.research.calibration); default: the synthetic regression set",
    )
    parser.add_argument("--out", help="Write the full report as JSON to this file")
    args = parser.parse_args()
    model = ResearchModel.from_environment()
    if model is None:
        raise SystemExit(
            "Set OPENROUTER_API_KEY and OPENROUTER_MODEL to evaluate live verification"
        )
    path = args.cases or (
        Path(__file__).resolve().parents[2] / "docs/research/verification-cases.json"
    )
    cases, skipped = load_cases(path)
    report = asyncio.run(evaluate(model, cases))
    report["unlabelled_rows_skipped"] = skipped
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text)
        summary = {k: report[k] for k in ("model", "total", "accuracy", "false_support_rate", "per_label", "errors")}
        print(json.dumps(summary, indent=2))
    else:
        print(text)
    # The synthetic regression set must pass exactly; your own labels just get a report.
    if args.cases is None and report["correct"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
