# Measuring claim-check accuracy in your field

Indra's claim checks are only as good as the model's judgments on your field's papers, and no fixture can tell you that. These two commands turn a real session into an accuracy report.

```sh
# 1. Export claims with the passages Indra stored as evidence (no model calls)
uv run python -m src.research.calibration export <SESSION_ID> --out labels.csv

# 2. In a spreadsheet, fill "expected" with supports / contradicts / insufficient,
#    judging only the passage shown. Leave rows blank to skip them.

# 3. Score the configured model against your labels (one model call per labelled row)
uv run python -m src.research.evaluate --cases labels.csv --out report.json
```

The command prints a summary and writes the full report:

- `accuracy`: share of rows where the model's verdict matched your label.
- `false_support_rate`: of the passages the model said **support** a claim, the share your labels say do not. This is the error that matters most, because supported claims are promoted in the ledger and exports.
- `per_label` and `confusion`: where the misses are (for example, contradictions read as insufficient).
- `errors`: answers that were malformed or quoted text not in the passage; those claims stay for review in a real run.

Labelling 50 rows takes about 20 minutes and uses 50 model calls (the free OpenRouter tier allows 50 per day). Re-run the same file after changing `OPENROUTER_MODEL` to compare models on identical cases. Without `--cases`, the command runs the 12-case synthetic regression set and exits non-zero on any mismatch.

A score on one session's claims describes that session's kind of literature. It is not a general benchmark, and Indra does not use it to adjust confidence.
