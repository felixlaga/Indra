"""A checkpointed search → full text → synthesis → evidence research run."""

import asyncio

from ..api.claim_validation_models import ClaimAutoValidationRequest
from ..api.claim_validation_routes import validate_automatically
from ..claims import ClaimExtractor
from .full_text import fetch_full_text
from .model import ModelUnavailable
from .models import ClaimDraft, PaperResult, PaperSynthesis, ResearchLimits, stable_id
from .providers import search_provider


class ModelBudgetExhausted(ModelUnavailable):
    """The session's model-call budget is spent."""


class BudgetedModel:
    """Reserve each model request durably so retries cannot reset the call budget."""

    def __init__(self, model, repository, leased, limit):
        self.model, self.repository, self.leased, self.limit = (
            model,
            repository,
            leased,
            limit,
        )

    async def generate(self, *args):
        used = self.repository.get_job(self.leased.id).result.get("model_calls", 0)
        if used >= self.limit:
            raise ModelBudgetExhausted(
                f"The model-call budget of {self.limit} was reached"
            )
        self.repository.heartbeat_research(self.leased, {"model_calls": used + 1})
        return await self.model.generate(*args)


def excerpt_synthesis(paper, text, limits):
    """A source excerpt is useful without implying an LLM or verification ran."""

    excerpt = paper.abstract or " ".join(text.split())
    drafts = ClaimExtractor().extract(
        excerpt[: limits.max_source_chars], max_claims=limits.max_claims
    )
    synthesis = PaperSynthesis(
        summary="Source excerpt (not model-validated):\n" + excerpt[:3000],
        claims=[
            ClaimDraft(text=d.text[:1500], claim_type=d.claim_type) for d in drafts
        ],
    )
    provenance = {
        "provider": "local",
        "model": "source_excerpt",
        "prompt_name": "source_excerpt",
        "prompt_version": "v1",
    }
    return synthesis, provenance


class ResearchPipeline:
    def __init__(
        self,
        repository,
        model=None,
        *,
        search=search_provider,
        full_text=fetch_full_text,
    ):
        self.repository, self.model = repository, model
        self.search, self.full_text = search, full_text

    async def run(self, leased):
        repo = self.repository
        session = repo.get_session(leased.session_id)
        limits = ResearchLimits.model_validate(session.parameters.get("research", {}))
        model = (
            BudgetedModel(self.model, repo, leased, limits.max_model_calls)
            if self.model
            else None
        )
        progress = dict(repo.get_job(leased.id).result)
        query = (
            repo.get_branch(leased.branch_id).query
            if leased.branch_id
            else session.initial_query
        )

        def checkpoint(**values):
            progress.update(values)
            repo.heartbeat_research(leased, values)

        def stop_model(exc):
            # Keep finished work; everything after this point is explicitly left for review.
            nonlocal model
            model = None
            checkpoint(model_stop_reason=str(exc))

        if progress.get("model_stop_reason"):
            model = None

        snapshot = repo.get_session_snapshot(session.id)
        selected = [p.paper for p in snapshot.papers if p.branch_id == leased.branch_id]
        if not progress.get("search_complete"):
            checkpoint(stage="search", message="Searching academic sources")
            outcomes = await asyncio.gather(
                *(
                    self.search(name, query, session.filters, limits)
                    for name in session.source_providers
                ),
                return_exceptions=True,
            )
            warnings, found, successes = [], [], 0
            for name, outcome in zip(session.source_providers, outcomes):
                if isinstance(outcome, Exception):
                    warnings.append(f"{name}: {type(outcome).__name__}")
                else:
                    successes += 1
                    found.extend(outcome)
            if not successes:
                raise RuntimeError(
                    "All selected search providers failed: " + "; ".join(warnings)
                )
            unique = {p.canonical_key: p for p in selected}
            for paper in found:
                unique.setdefault(paper.canonical_key, paper)
            selected = list(unique.values())[: limits.max_papers]
            for paper in selected:
                paper.id = repo.save_research_paper(leased, PaperResult(paper=paper))
            checkpoint(
                search_complete=True,
                selected_paper_ids=[p.id for p in selected],
                warnings=warnings,
                message=f"Selected {len(selected)} papers",
                stage="select",
            )
        else:
            selected = [
                repo.get_paper(paper_id)
                for paper_id in progress.get("selected_paper_ids", [])
            ]

        for number, paper in enumerate(selected, 1):
            summary_id = stable_id(leased.id, paper.id, "summary")
            if any(
                s.id == summary_id
                for s in repo.get_session_snapshot(session.id).summaries
            ):
                continue
            checkpoint(
                stage="full_text",
                paper_id=paper.id,
                paper_number=number,
                total_papers=len(selected),
                message=f"Reading {paper.title}",
            )
            chunks, note, parse_status = [], None, "unavailable"
            try:
                async with asyncio.timeout(limits.provider_timeout_seconds):
                    chunks, note = await self.full_text(paper)
                parse_status = "parsed" if chunks else "unavailable"
            except Exception as exc:
                note = f"PDF retrieval failed ({type(exc).__name__}); abstract-only coverage."
                parse_status = "failed"
            text = "\n\n".join(c.text for c in chunks) or paper.abstract or ""
            if not text:
                repo.save_research_paper(
                    leased,
                    PaperResult(
                        paper=paper,
                        source_note="No accessible source text.",
                        parse_status=parse_status,
                    ),
                )
                continue
            checkpoint(
                stage="summarize", message=f"Extracting claims from {paper.title}"
            )
            synthesis = None
            if model:
                try:
                    synthesis, provenance = await model.generate(
                        PaperSynthesis,
                        f"Summarize this source and extract up to {limits.max_claims} atomic claims. Preserve uncertainty. "
                        "Each claim must be independently checkable. Hypotheses must have claim_type hypothesis.",
                        {
                            "title": paper.title,
                            "text": text[: limits.max_source_chars],
                            "source_scope": "full_text_excerpt"
                            if chunks
                            else "abstract",
                        },
                    )
                    synthesis.claims = synthesis.claims[: limits.max_claims]
                except ModelUnavailable as exc:
                    stop_model(exc)
                except ValueError:
                    # Malformed or refused output for one source must not end the session.
                    note = " ".join(
                        filter(
                            None,
                            [note, "Model output was invalid; kept a source excerpt."],
                        )
                    )
            if synthesis is None:
                synthesis, provenance = excerpt_synthesis(paper, text, limits)
            repo.save_research_paper(
                leased,
                PaperResult(
                    paper=paper,
                    chunks=chunks,
                    source_url=paper.open_access_pdf_url,
                    source_note=note,
                    parse_status=parse_status,
                    synthesis=synthesis,
                    provenance=provenance,
                ),
            )

        # Judge after all selected sources have been persisted, including opposing papers.
        verified = set(progress.get("verified_claim_ids", []))
        for_review = set(progress.get("review_claim_ids", []))
        summary_ids = {stable_id(leased.id, p.id, "summary") for p in selected}
        for claim in repo.list_claims(session.id):
            if (
                claim.summary_id not in summary_ids
                or claim.id in verified
                or claim.status.value == "speculative"
            ):
                continue
            checkpoint(
                stage="verify",
                message="Checking claims against persisted source passages",
            )
            request = ClaimAutoValidationRequest(top_k=3)
            try:
                await validate_automatically(repo, claim.id, request, model, leased)
            except (ModelUnavailable, ValueError) as exc:
                if isinstance(exc, ModelUnavailable):
                    stop_model(exc)
                # Attach retrieved passages unjudged so the claim stays reviewable.
                await validate_automatically(repo, claim.id, request, None, leased)
                for_review.add(claim.id)
            else:
                if model is None and self.model:
                    for_review.add(claim.id)
            verified.add(claim.id)
            checkpoint(
                verified_claim_ids=sorted(verified),
                review_claim_ids=sorted(for_review),
            )
        message = f"Research finished with {len(selected)} selected papers"
        if self.model is None:
            mode = "retrieval_only"
        elif progress.get("model_stop_reason") or for_review:
            mode = "model_partial"
            reason = progress.get("model_stop_reason")
            message += (
                f". {reason}" if reason else ". Some model answers were invalid"
            ) + f"; {len(for_review)} claims were left for review"
        else:
            mode = "model"
        checkpoint(stage="complete", message=message, verification_mode=mode)
