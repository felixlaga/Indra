# Phase 5: Scout branches and cross-paper synthesis

Phases 1–4 ran one bounded search → read → check pass per session. Phase 5 lets the product worker follow up on what it finds, then write a session-level synthesis with hypotheses that connect several papers.

## What happens in a session

1. **Root branch.** As before: search, select up to `max_papers`, read full text, summarize, extract claims, check them against every stored passage.
2. **Scout planning.** If a model is configured and the branch is shallower than `max_depth`, the model sees the branch's checked claims (by short alias, `C1`, `C2`…) and the session question, and proposes at most three follow-up search queries, each tied to a contradiction, missing evidence, an unexplained mechanism, a method comparison, a limitation or an adjacent area. The worker drops proposals that repeat an existing branch question (token overlap ≥ 0.7) or cite claims that do not exist, and records each dropped proposal with its reason.
3. **Scout branches.** Each accepted question becomes a child branch with its own `branch_continue` job. The branch, its job and the decision are written in one transaction that also enforces the session-wide `max_branches` limit, so concurrent branches cannot overshoot it. Scout branches read up to `branch_papers` new papers and skip papers already read elsewhere in the session. Their claims are checked against all session passages, including the root's.
4. **Synthesis.** When the last branch job finishes, the repository queues one `session_synthesis` job (a partial unique index prevents a second). The model writes an overview and proposes up to five hypotheses. A hypothesis is kept only if its cited supporting claims span at least two stored papers; others are dropped and recorded. The overview is stored as a `session` summary, the hypotheses in `hypotheses` with `hypothesis_support` links, both labelled not validated and speculative.

Every decision — including "no follow-ups because the model is not configured", "the branch limit was reached" or "the model's plan was invalid" — is stored in `agent_decisions` with its rationale, dropped alternatives and provenance, and shown in the session hub.

## Budget

`max_model_calls` is now a session-wide limit, reserved durably under the session row lock so concurrent branches cannot exceed it. A few calls (one each for planning and synthesis, at most a third of the budget) are reserved; ordinary calls stop before that reserve. The remainder is split between branches by their paper allowance, so the root cannot starve the Scouts. Reaching a branch's share or the session limit leaves the remaining claims for review, as in Phase 1, and the run completes.

Claim checking now sends all retrieved passages for a claim in one call (`EvidenceJudgments`) instead of one call per passage, roughly a third of the previous cost. A quote is accepted when it appears in its passage after normalizing whitespace, Unicode compatibility forms and hyphenated line breaks (`com-⏎parable`). A judgment whose quote is not found only invalidates that passage; an answer that references unknown or repeated passage numbers invalidates the claim's check.

## Parameters

Under `parameters.research`, validated by the API:

| Field | Default | Range | Meaning |
| --- | --- | --- | --- |
| `max_depth` | 1 | 0–3 | Scout levels below the root; 0 disables Scouts |
| `max_branches` | 3 | 0–12 | Child branches per session, including manual splits |
| `branch_papers` | 3 | 1–20 | Papers read per Scout branch |
| `synthesize` | true | — | Queue session synthesis after the last branch |
| `max_model_calls` | 30 | 1–100 | Session-wide model calls |

The session form offers three presets: **Quick** (no Scouts or synthesis, 30 calls), **Standard** (one level, three branches, 45 calls) and **Deep** (two levels, eight branches, 100 calls). Without a model key every preset behaves like Quick, and the session explains why no follow-ups were opened.

## Failure behaviour

- A Scout branch or synthesis job that fails after its retries completes the session with a warning event; the root's results and other branches stay usable. A root failure still fails the session.
- A rate-limited provider (see Phase 1) also stops planning, but synthesis is still attempted once, in its own job.
- Recording the same decision twice (a retried job) returns the branches opened the first time. Synthesis is skipped when its summary already exists.
- Pause, resume and cancel apply to Scout and synthesis jobs like any other session job.

## Upgrade

Apply migration `0004_research_scouts.sql` with the same mode as before (`uv run python -m src.api.migrate`, plus `--without-vectors` if the database was created that way). It widens the job-type check, adds the one-synthesis-per-session index, and adds `missing_evidence`/`next_steps` to hypotheses and `details` to agent decisions.

## Verification — October 8, 2026

- 176 backend tests against memory and real Postgres, including Scout creation and deduplication, depth limits, recorded no-model and rate-limit decisions, the reserved planning and synthesis calls under a 4-call budget, idempotent decisions, branch limits enforced at write time, failed synthesis, one synthesis job when two branches finish concurrently, and concurrent model-call reservations never exceeding the budget.
- 24 frontend tests, TypeScript checking and the production build.
- A live run with `nvidia/nemotron-3-super-120b-a12b:free`, arXiv and a 10-call budget completed root → one Scout branch → synthesis. It exposed two problems fixed here: valid quotes rejected over PDF line-break hyphenation, and synthesis overviews that listed claim aliases (`C1, C2…`); aliases are now replaced with author–year citations.
- Browser checks on a clearly labelled synthetic fixture session (scripted model output, no network): synthesis card, Scout decision with dropped proposals, hypothesis inspector with its source, depth picker at desktop and 375 px width without horizontal overflow, no console errors.

Live model quality of Scout plans and hypotheses is not established by these checks. Hypotheses remain speculative planning aids.
