# Phase 8: Research exports

## Status

Implemented as the final roadmap phase.

## Export catalog

```http
GET /sessions/{session_id}/exports
```

The catalog lists every downloadable artifact, filename, media type, description, and whether validation status is preserved.

## Download endpoint

```http
GET /sessions/{session_id}/exports/{format_name}
```

Every response includes:

- `Content-Disposition: attachment`
- `Cache-Control: no-store`
- `X-ERLA-Validation-Preserved: true`

## Formats

| Format name | Artifact |
|---|---|
| `bibtex` | BibTeX bibliography |
| `ris` | RIS bibliography |
| `report-markdown` | Markdown research report |
| `literature-review-latex` | LaTeX literature-review outline |
| `annotated-bibliography` | Annotated bibliography in Markdown |
| `claim-ledger-csv` | Flat claim ledger CSV |
| `claim-ledger-json` | Structured claim and evidence ledger JSON |
| `research-map-json` | Complete Phase 6 research-map JSON |

## Validation-preservation policy

Claim-bearing exports never remove claim state.

- Markdown reports mark every exported claim with its current status.
- LaTeX outlines use explicit claim-status labels.
- Annotated bibliographies show status and evidence count for each paper-linked claim.
- CSV and JSON ledgers preserve the original status, confidence, evidence relationships, and whether the claim is eligible for cautious synthesis.
- Speculative hypotheses are labelled `SPECULATIVE`, include missing evidence, and are not presented as established findings.
- Contradicted, `not_found`, `needs_review`, and speculative claims remain unsupported in exported artifacts.

Bibliography formats contain paper metadata rather than generated factual claims. They include a note directing users to the claim ledger for validation state.

## Dashboard

The export center is available at:

```text
/sessions/{session_id}/exports
```

It groups artifacts into:

- Bibliographies
- Research documents
- Data exports

Each card displays the output filename, media type, description, and validation-preservation status.

## Determinism

Exports are generated only from the durable session snapshot and deterministic Phase 6/7 builders. The download request does not call external paper providers or language models.

## Verification

```bash
python -m pytest -q \
  test_api_cors.py \
  test_api.py \
  test_claim_evidence_retrieval.py \
  test_research_map.py \
  test_research_advice.py \
  test_exports.py

cd apps/web
npm run typecheck
npm test
npm run build
```

The export test suite verifies:

- the complete roadmap catalog;
- attachment headers and validation-preservation headers;
- explicit speculative/unsupported labels;
- CSV and JSON status preservation;
- parseable bibliography and research-map outputs;
- rejection of unknown formats.

## Known limits

- BibTeX and RIS generation uses the paper metadata available in the session and cannot infer missing bibliographic fields.
- The LaTeX output is an outline, not a submission-ready manuscript.
- Exports are generated synchronously because the current artifacts are text-only and bounded by session size. Large-session asynchronous export jobs remain a production-hardening option.
- A ZIP bundle, DOCX, PDF rendering, and citation-style customization are outside the Phase 8 roadmap scope.
