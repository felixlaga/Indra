"""Run the checked-in synthetic verifier regression set against a configured model."""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from ..claims import EvidenceCandidate, EvidenceRetriever
from ..claims.semantic_verifier import judge_passages
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
            error = None
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
        "correct": sum(r["correct"] for r in results),
        "total": len(results),
        "note": "Synthetic regression set; not a calibrated scientific-domain benchmark.",
        "results": results,
    }


def main():
    load_dotenv()
    model = ResearchModel.from_environment()
    if model is None:
        raise SystemExit(
            "Set OPENROUTER_API_KEY and OPENROUTER_MODEL to evaluate live verification"
        )
    cases = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/research/verification-cases.json"
        ).read_text()
    )
    report = asyncio.run(evaluate(model, cases))
    print(json.dumps(report, indent=2))
    if report["correct"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
