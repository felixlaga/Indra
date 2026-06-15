# ERLA Code Style

## 1. General style

Write code that is explicit, typed, and boring.

Prioritize maintainability over cleverness.

## 2. Python style

Use:

- Type hints.
- Pydantic models for API/data validation.
- Dataclasses only for simple internal runtime structures.
- Explicit exceptions.
- Structured logging.
- Small functions.

Avoid:

- Hidden global state.
- Broad `except Exception` without logging and recovery.
- Hard-coded model names deep in business logic.
- Hard-coded API keys.
- Giant prompt strings mixed into orchestration code.
- Silent fallback behavior.

## 3. TypeScript style

Use when frontend exists:

- TypeScript strict mode.
- Typed API clients.
- Small React components.
- Server/client component separation where relevant.
- Reusable UI primitives.

Avoid:

- `any` unless justified.
- Large all-in-one dashboard components.
- Business logic embedded in visual components.
- UI state that duplicates server state without reason.

## 4. Naming

Use domain names consistently:

- Project.
- ResearchSession.
- Branch.
- Scout.
- Paper.
- Summary.
- Claim.
- Evidence.
- Validation.
- Hypothesis.
- AgentDecision.
- Event.
- Export.

Do not invent multiple names for the same concept.

## 5. Prompt management

Prompts should be versioned.

Current prompts are embedded in source files. That is acceptable for a prototype but should be migrated as the product matures.

Recommended future structure:

```txt
src/prompts/
  paper_selection.md
  summarization.md
  claim_extraction.md
  claim_verification.md
  branch_management.md
  hypothesis_generation.md
  reflection.md
  research_advisor.md
```

Every prompt-backed output should store prompt version.

## 6. Logging

Logs should include:

- session_id where available.
- branch_id where available.
- paper_id where available.
- job_id where available.
- component name.
- event type.

Do not log secrets or full private user documents unnecessarily.

## 7. Error messages

Internal errors should be detailed.

User-facing errors should be clear and actionable.

Bad:

```txt
Error
```

Good:

```txt
PDF parsing failed for this paper. The abstract is still available. You can retry parsing or upload the PDF manually.
```

## 8. Comments

Use comments to explain why, not what.

Bad:

```python
# increment i
i += 1
```

Good:

```python
# Keep failed paper jobs in the session so the user can retry them later.
```

## 9. Tests

New domain logic requires tests.

If a feature changes validation, claims, citations, or branch decisions, add tests.

## 10. Dependency rules

Add dependencies only when they solve a clear problem.

Before adding a dependency, consider:

- Maintenance status.
- License.
- Security.
- Bundle size for frontend.
- Runtime cost.
- Whether the standard library is enough.

## 11. Formatting

Recommended for Python:

```txt
ruff
black or ruff format
pytest
mypy or pyright when practical
```

Recommended for TypeScript:

```txt
eslint
prettier
tsc
```

## 12. Final rule

Code should make ERLA more trustworthy, inspectable, and useful for real research.
