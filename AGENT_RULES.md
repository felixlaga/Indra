# ERLA Agent Rules

## 1. Purpose

ERLA uses agents/components to search, select, summarize, validate, branch, reflect, synthesize, and advise.

Agents must be bounded, auditable, and evidence-aware. They are not unrestricted chatbots.

## 2. Current agent-like components

The current repository already contains:

- `InnerLoop`: search, paper selection, summarization, validation, hypothesis mode.
- `IterationLoop`: citation/reference expansion.
- `MasterAgent`: branch lifecycle orchestration.
- `BranchManager`: branch creation, splitting, pruning, status updates.
- `ManagingAgent`: OpenRouter-backed branch continue/split/wrap-up decisions.
- `ReflectionAgent`: coverage/gap evaluation after summarization.
- `HypothesisGenerator`: hypothesis generation from validated summaries.

These should be preserved and made more auditable rather than replaced blindly.

## 3. Universal agent rules

Every agent must:

1. Follow the product thesis: research navigation with epistemic traceability.
2. Prefer evidence over eloquence.
3. Store consequential decisions.
4. Expose concise rationale.
5. Respect validation rules.
6. Avoid unsupported factual claims.
7. Label speculation.
8. Fail visibly.
9. Preserve partial results.
10. Use structured outputs whenever possible.

## 4. Prohibited behavior

Agents must not:

- Invent papers.
- Invent citations.
- Invent page numbers.
- Invent source passages.
- Claim novelty without evidence.
- Hide contradictions.
- Promote unsupported claims.
- Delete failed outputs silently.
- Make irreversible decisions without storing rationale.
- Use hidden state as evidence.
- Treat citation count as proof of truth.
- Treat model confidence as factual support.

## 5. Agent decision records

Every important decision must create an `agent_decision` record once durable storage exists.

Required fields:

- decision_type.
- input_summary.
- decision.
- rationale.
- alternatives.
- confidence.
- model.
- prompt_version.
- token_usage if available.
- cost if available.

Do not store hidden chain-of-thought. Store a concise rationale suitable for user inspection.

## 6. Search Planner

Future component.

Responsibilities:

- Generate search queries and filters.
- Use multiple query variants when useful.
- Respect user constraints.
- Record search rationale.

Inputs:

- User query.
- Project context.
- Branch context.
- Existing papers.
- Existing gaps.
- User constraints.

Outputs:

- Search query.
- Providers.
- Filters.
- Rationale.
- Expected coverage.

## 7. Paper Selector

Current behavior is inside `InnerLoop`.

Responsibilities:

- Select which candidate papers should be processed deeply.
- Balance relevance, diversity, recency, foundational value, and coverage.

Rules:

- Do not select only by citation count.
- Do not select only recent papers unless requested.
- Avoid duplicate or near-duplicate papers.
- Prefer papers with accessible abstracts/full text when possible.
- Keep enough diversity to avoid tunnel vision.

## 8. Summarizer

Current behavior is in `src/summarize.py` and `InnerLoop._summarize_and_validate`.

Responsibilities:

- Summarize paper content from source text.
- Prefer concise, structured summaries.
- Avoid unsupported inference.

Rules:

- Use only provided source text for factual claims.
- Mark uncertainty.
- Do not claim a paper says something unless source text supports it.
- Prefer omission over unsupported detail.

## 9. Claim Extractor

An initial deterministic extraction scaffold exists. The future worker/agent version must preserve the same safety rules.

Responsibilities:

- Convert summaries and syntheses into atomic claims.
- Classify claim type.
- Preserve link to source paper and summary.

Rules:

- One factual statement per claim.
- Split compound claims.
- Separate factual claims from hypotheses.
- Avoid vague claims that cannot be checked.

## 10. Claim Verifier

An initial deterministic supplied-evidence verifier scaffold exists. The future worker/agent version must preserve the same safety rules while adding automated evidence retrieval and richer validation.

Responsibilities:

- Validate claims against source evidence.
- Attach evidence passages.
- Assign claim status.

Rules:

- Use source evidence only.
- If evidence is missing, mark `not_found`.
- If evidence partially supports the claim, mark `weakly_supported`.
- If evidence conflicts, mark `contradicted`.
- Never upgrade unsupported claims because they sound plausible.

## 11. Branch Manager / Managing Agent

Current components exist.

Allowed actions:

```txt
continue
split
prune
wrap_up
switch_to_hypothesis
request_user_input
```

Rules:

- Split only when it improves research coverage.
- Prune branches that are stale, redundant, irrelevant, or low-value.
- Preserve rationale for every split/prune.
- Do not create uncontrolled branch explosion.
- Respect max branch limits.
- Prefer fewer high-quality branches over many shallow branches.

## 12. Reflection Agent

Current component exists.

Responsibilities:

- Assess coverage after summarization.
- Identify gaps.
- Suggest searches.
- Flag low-value papers.

Rules:

- Gap suggestions are hypotheses until additional evidence is gathered.
- Reflection output must be stored and displayed when user-facing.
- Do not treat coverage score as objective truth.

## 13. Hypothesis Generator

Current component exists.

Responsibilities:

- Generate possible research directions from validated evidence.

Rules:

- Hypotheses are speculative by default.
- Do not present hypotheses as facts.
- Do not claim novelty unless explicitly checked.
- Include what would falsify or weaken the hypothesis.
- Prefer actionable hypotheses.

## 14. Research Advisor

Future component.

Responsibilities:

- Help the user decide what to read, learn, and investigate next.
- Generate reading plans and research directions.

Rules:

- Ground recommendations in retrieved papers and claims.
- Clearly separate advice from evidence.
- Explain tradeoffs.
- Avoid generic advice.
- Prefer concrete next steps.

## 15. Output format

Agents should return JSON-compatible structured output whenever possible.

Example:

```json
{
  "decision": "split",
  "rationale": "The branch contains two distinct methodological clusters.",
  "confidence": 0.78,
  "new_branches": [
    {
      "label": "Wave-optics lensing theory",
      "query": "wave optics gravitational wave lensing theory amplification factor"
    },
    {
      "label": "Small-scale dark matter applications",
      "query": "gravitational wave lensing small scale dark matter constraints"
    }
  ]
}
```

## 16. Testing

Each agent must have tests for:

- Normal case.
- Empty input.
- Malformed model output.
- Unsupported claim.
- Contradictory evidence.
- Provider failure.
- Timeout.
- Retry behavior.

## 17. Final rule

If an agent is unsure, it should say what is uncertain, what evidence is missing, and what action would reduce uncertainty.
