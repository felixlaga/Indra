# Phase 5: Claim-level validation MVP

## Status

Implemented as an inspectable validation layer over the existing claim, evidence, event, and paper contracts.

## Scope delivered

- Deterministic evidence retrieval from persisted paper abstracts and metadata.
- Conservative relation classification: `supports`, `weakly_supports`, `contradicts`, `mentions`, or `insufficient`.
- Existing claim-status decisions remain centralized in `ClaimVerifier`.
- Automatic validation endpoint: `POST /claims/{claim_id}/validate/auto`.
- Claim inspection endpoint: `GET /claims/{claim_id}/inspection`.
- Claim inspector page under `/claims/[claimId]`.
- Evidence passage viewer with source type, section/page locator, relation, score, and paper link.
- Validation trace reconstructed from durable `claim_validated` events.
- Clickable claim ledger in the session dashboard.
- Explicit policy messages for supported, weak, contradicted, missing, speculative, and review-required claims.
- Automatic validation refuses to promote speculative or hypothesis claims.

## Retrieval policy

The retriever is deliberately transparent and non-generative. It:

1. Tokenizes the atomic claim and persisted passages.
2. Removes common stop words.
3. Measures the fraction of content-bearing claim terms found in each passage.
4. Applies a small source-hierarchy preference to abstracts over metadata.
5. Detects only a narrow contradiction case: strong lexical overlap with opposite negation.
6. Stores only passages above the configured retrieval threshold.

The current relation thresholds are conservative heuristics:

- `supports`: lexical coverage at least 0.72.
- `weakly_supports`: lexical coverage at least 0.45.
- `mentions`: lexical coverage at least 0.25.
- `insufficient`: below 0.25 but above the retrieval threshold.
- `contradicts`: coverage at least 0.55 with opposite negation state.

These scores are evidence-retrieval diagnostics, not calibrated probabilities and not semantic proof.

## API examples

Retrieve and validate against the claim's paper, or against session papers when the claim has no paper:

```http
POST /claims/{claim_id}/validate/auto
Content-Type: application/json

{
  "top_k": 5,
  "min_score": 0.15,
  "include_session_papers": true
}
```

Inspect the complete user-facing validation state:

```http
GET /claims/{claim_id}/inspection
```

The inspection response contains:

- Current atomic claim and status.
- Stored evidence passages.
- Validation history derived from immutable session events.
- Primary paper metadata when linked.

## Safety behavior

- No passage means `not_found`; the claim is not promoted.
- Mention-only or insufficient passages do not promote a claim.
- Contradictory evidence takes precedence over supporting evidence in the existing verifier.
- Speculative and hypothesis claims return HTTP 409 from automatic validation.
- Re-running validation preserves earlier evidence and event traces rather than erasing history.
- The UI always shows claim status and evidence before downstream use.

## Verification

```bash
python -m pytest -q \
  test_api_cors.py \
  test_api.py \
  test_claim_evidence_retrieval.py

cd apps/web
npm run typecheck
npm test
npm run build
```

## Known limits

- The repository schema already contains `paper_documents`, `paper_chunks`, and `validations`, but the current product repository contract does not yet expose full-text chunks to this API route. Phase 5 retrieval therefore uses persisted abstracts and metadata only.
- The lexical relation classifier is deterministic and auditable, but it is not a replacement for a calibrated NLI or domain-specific verifier.
- Validation traces are reconstructed from durable `claim_validated` events. A later hardening step can additionally materialize the existing `validations` table as a first-class read model.
- Manual override records, full-text retrieval, multi-passage high-impact claim policy, and contradiction linking across claims remain follow-up work.
