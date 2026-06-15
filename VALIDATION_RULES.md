# ERLA Validation Rules

## 1. Purpose

ERLA must optimize for epistemic integrity.

The current repository already has token-level HaluGate validation and NLI-based filtering. That is valuable, but production ERLA needs a stricter claim-level validation layer.

This file defines the rules that all agents, code, prompts, and UI components must follow.

## 2. Core rule

No factual claim may be promoted to the research knowledge base unless it has source evidence or is explicitly marked as unverified/speculative.

## 3. Definitions

### 3.1 Factual claim

A statement about the world, a paper, a method, a result, a dataset, a theory, or a citation relationship that can be checked against evidence.

Example:

> The paper uses a transformer encoder.

### 3.2 Speculative claim

A possible idea, hypothesis, interpretation, or research direction that is not directly established by source evidence.

Example:

> This method may be adaptable to gravitational-wave lensing.

### 3.3 Evidence

A source passage or metadata field used to support or contradict a claim.

Evidence may come from:

- Abstract.
- Full text.
- PDF text.
- Section.
- Figure caption.
- Table text.
- Metadata.
- Citation graph.
- User-provided source.

### 3.4 Groundedness

Groundedness estimates how much generated text is supported by source context.

The current character-span groundedness score is useful but insufficient for final product trust. Claim-level validation must be added.

## 4. Claim statuses

Allowed statuses:

```txt
supported
weakly_supported
contradicted
not_found
speculative
needs_review
```

Rules:

- `supported` claims may appear in final synthesis.
- `weakly_supported` claims may appear only with caution.
- `contradicted` claims must be surfaced as contradictions, not hidden.
- `not_found` claims must not be presented as fact.
- `speculative` claims must be labeled as speculation.
- `needs_review` claims require user or system review before use.

## 5. Summary validation pipeline

Paper summaries must be generated only from available source text.

The summary pipeline must:

1. Gather source context.
2. Generate summary.
3. Validate summary against source context using HaluGate where available.
4. Extract atomic claims.
5. Validate atomic claims.
6. Store summary with validation metadata.
7. Store claims separately.

A summary may be shown if it is partially validated, but the UI must show validation status.

## 6. Atomic claim extraction

Generated summaries and syntheses must be decomposed into atomic claims.

Extracted factual claims start as `needs_review` until a verifier attaches evidence. Extracted hypotheses or speculative statements must be marked `speculative`.

The current API scaffold can validate a claim against explicitly supplied evidence passages. It stores those evidence records in process memory and uses deterministic relation rules: `contradicts` marks a claim `contradicted`, `supports` marks it `supported`, `weakly_supports` marks it `weakly_supported`, and `mentions` or `insufficient` must not promote the claim. Production validation still needs automated evidence retrieval, durable evidence storage, and richer verifier traces.

Bad claim:

> The paper introduces a new method, evaluates it on several datasets, outperforms baselines, and discusses limitations.

Good atomic claims:

- The paper introduces a new method.
- The paper evaluates the method on several datasets.
- The paper compares the method against baselines.
- The paper discusses limitations.

Each atomic claim must be validated separately.

## 7. Evidence requirements

Each supported claim should have:

- At least one evidence passage.
- Source paper ID.
- Chunk ID if available.
- Page or section if available.
- Relation type.
- Confidence score.

For high-impact claims, prefer multiple evidence passages.

High-impact claims include:

- Claims about novelty.
- Claims about state of the art.
- Claims about superiority.
- Claims about consensus.
- Claims about contradictions.
- Claims used to recommend research directions.

## 8. Hypothesis rules

Hypotheses are allowed to be creative, but they must not be presented as facts.

Each hypothesis must include:

- Supporting claims.
- Missing evidence.
- Confidence.
- Testability.
- Risk.
- Suggested next validation step.

A hypothesis may not claim novelty unless novelty was explicitly checked against literature. Even then, use cautious language.

Allowed language:

- Potentially underexplored.
- Appears weakly covered in the current session.
- May be promising based on the retrieved papers.

Disallowed language unless proven:

- Novel.
- Unexplored.
- First.
- Never studied.
- Guaranteed.

## 9. Contradiction handling

When two claims conflict, ERLA must:

1. Store both claims.
2. Link them through contradiction relation.
3. Surface the contradiction in the UI.
4. Avoid forcing false consensus.
5. Explain what evidence supports each side.

## 10. Citation rules

A citation does not automatically support a claim.

If Paper A cites Paper B, that only proves a citation relation. It does not prove agreement unless text evidence shows agreement.

## 11. Source hierarchy

Prefer evidence from:

1. Full paper text.
2. Abstract.
3. Metadata.
4. Citation graph.
5. Model inference.

Model inference alone cannot support factual claims.

## 12. Validation failure rules

If validation fails:

- Do not delete the generated content.
- Store the failure.
- Show failure status.
- Allow retry.
- Do not promote failed content to final synthesis.

## 13. Manual override

Users may manually mark claims as reviewed, accepted, or rejected.

Manual overrides must be stored separately from automatic validation.

Do not erase original validation state.

## 14. Export rules

Exports must preserve validation status.

A literature review export must not silently include unsupported claims.

Every exported factual claim should include source reference or be labeled as unverified.

## 15. Acceptance criteria

A validation feature is acceptable only if:

1. It stores validation status.
2. It stores source evidence.
3. It exposes evidence in the UI.
4. It distinguishes factual and speculative claims.
5. It handles unsupported claims safely.
6. It is testable.
