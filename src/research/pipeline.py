"""A checkpointed search → full text → synthesis → evidence research run.

Each branch job reads and checks its own sources, then may open Scout branches
for follow-up questions. When the last branch finishes, a session synthesis job
writes an overview and cross-paper hypotheses.
"""

import asyncio

from ..api.claim_validation_models import ClaimAutoValidationRequest
from ..api.claim_validation_routes import validate_automatically
from ..api.models import JobType
from ..claims import ClaimExtractor
from .full_text import fetch_full_text
from .model import ModelRateLimited, ModelUnavailable
from .models import (
    ClaimDraft,
    PaperResult,
    PaperSynthesis,
    ResearchLimits,
    ScoutPlan,
    SessionSynthesis,
    SynthesisRecord,
    stable_id,
)
from .providers import search_provider
from .scouts import (
    PLAN_INSTRUCTION,
    SYNTHESIS_INSTRUCTION,
    accept_plan,
    accept_synthesis,
    plan_input,
    skipped_plan,
    skipped_synthesis,
    synthesis_input,
)


class ModelBudgetExhausted(ModelUnavailable):
    """The session's model-call budget, or this branch's share of it, is spent."""


class BudgetedModel:
    """Reserve each model request durably so retries cannot reset the call budget.

    Ordinary calls stay within the branch's share and leave the reserved calls for
    planning and synthesis; priority calls may use the reserve.
    """

    def __init__(self, model, repository, leased, limits, *, root):
        self.model, self.repository, self.leased = model, repository, leased
        self.limits, self.root = limits, root

    async def generate(self, *args, priority=False):
        limits = self.limits
        exhausted = self.repository.reserve_model_call(
            self.leased,
            limit=limits.max_model_calls,
            reserved=0 if priority else limits.reserved_model_calls(),
            job_limit=None if priority else limits.branch_model_calls(root=self.root),
        )
        if exhausted == "branch":
            raise ModelBudgetExhausted(
                "This branch's share of the model-call budget was reached"
            )
        if exhausted:
            raise ModelBudgetExhausted(
                f"The model-call budget of {limits.max_model_calls} was reached"
            )
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

    async def run(self, leased) -> bool:
        """Run one job; True asks the repository to queue session synthesis when last."""

        session = self.repository.get_session(leased.session_id)
        limits = ResearchLimits.model_validate(session.parameters.get("research", {}))
        if leased.job_type == JobType.SESSION_SYNTHESIS:
            await self._synthesize(leased, session, limits)
            return False
        await self._research_branch(leased, session, limits)
        return self.model is not None and limits.synthesize

    async def _research_branch(self, leased, session, limits):
        repo = self.repository
        branch = repo.get_branch(leased.branch_id) if leased.branch_id else None
        root = branch is None or branch.parent_branch_id is None
        budgeted = (
            BudgetedModel(self.model, repo, leased, limits, root=root)
            if self.model
            else None
        )
        model = budgeted
        progress = dict(repo.get_job(leased.id).result)
        query = branch.query if branch else session.initial_query

        def checkpoint(**values):
            progress.update(values)
            repo.heartbeat_research(leased, values)

        def stop_model(exc):
            # Keep finished work; everything after this point is explicitly left for review.
            nonlocal model
            model = None
            checkpoint(model_stop_reason=str(exc), model_stop_kind=type(exc).__name__)

        if progress.get("model_stop_reason"):
            model = None

        snapshot = repo.get_session_snapshot(session.id)
        selected = [p.paper for p in snapshot.papers if p.branch_id == leased.branch_id]
        if not progress.get("search_complete"):
            checkpoint(stage="search", message=f"Searching academic sources for “{query}”")
            # Scout branches look for new literature; papers read elsewhere are already checked.
            known = (
                set()
                if root
                else {
                    p.paper.canonical_key
                    for p in snapshot.papers
                    if p.branch_id != leased.branch_id
                }
            )
            wanted = limits.papers_for(root=root)
            search_limits = limits.model_copy(
                update={"max_papers": min(limits.search_limit, wanted + len(known))}
            )
            outcomes = await asyncio.gather(
                *(
                    self.search(name, query, session.filters, search_limits)
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
                if paper.canonical_key not in known:
                    unique.setdefault(paper.canonical_key, paper)
            selected = list(unique.values())[:wanted]
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

        if branch is not None and limits.scouting and not progress.get("planned"):
            # A spent branch share still leaves the reserved planning call; a provider
            # quota does not.
            rate_limited = progress.get("model_stop_kind") == ModelRateLimited.__name__
            planner = None if rate_limited else budgeted
            await self._plan(leased, session, branch, limits, planner, checkpoint)
            checkpoint(planned=True)

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
        if progress.get("scout_message"):
            message += f". {progress['scout_message']}"
        checkpoint(stage="complete", message=message, verification_mode=mode)

    async def _plan(self, leased, session, branch, limits, planner, checkpoint):
        """Ask the model which follow-up questions this branch's findings justify."""

        repo = self.repository
        if branch.depth >= limits.max_depth:
            return
        if planner is None:
            if branch.parent_branch_id is None:
                repo.record_research_decision(
                    leased,
                    skipped_plan(
                        leased,
                        branch,
                        "Follow-up branches need a configured research model.",
                    ),
                    max_branches=limits.max_branches,
                )
            return
        branches = repo.list_branches(session.id)
        slots = limits.max_branches - sum(1 for b in branches if b.depth > 0)
        claims = [c for c in repo.list_claims(session.id) if c.branch_id == branch.id]
        reason = None
        if slots <= 0:
            reason = "The session's branch limit was already reached."
        elif not claims:
            reason = "This branch produced no claims to follow up."
        if reason:
            repo.record_research_decision(
                leased, skipped_plan(leased, branch, reason), max_branches=limits.max_branches
            )
            return
        slots = min(slots, 3)
        checkpoint(stage="plan", message="Deciding which follow-up questions to explore")
        papers = {p.paper.id: p.paper for p in repo.list_papers(session.id)}
        existing = [b.query for b in branches]
        aliases, data = plan_input(session, branch, claims, papers, existing, slots)
        try:
            plan, provenance = await planner.generate(
                ScoutPlan, PLAN_INSTRUCTION.format(slots=slots), data, priority=True
            )
        except ModelUnavailable as exc:
            decision = skipped_plan(leased, branch, f"{exc}; no follow-up branches were opened.")
        except ValueError:
            decision = skipped_plan(
                leased, branch, "The model's follow-up plan was invalid, so no branches were opened."
            )
        else:
            decision = accept_plan(
                plan,
                leased=leased,
                branch=branch,
                aliases=aliases,
                existing_queries=existing,
                slots=slots,
                provenance=provenance,
            )
        created = repo.record_research_decision(
            leased, decision, max_branches=limits.max_branches
        )
        if created:
            checkpoint(
                scout_message=f"Opened {len(created)} follow-up branch"
                + ("es" if len(created) != 1 else "")
            )

    async def _synthesize(self, leased, session, limits):
        """Write the session overview and keep cross-paper hypotheses."""

        repo = self.repository
        progress = dict(repo.get_job(leased.id).result)
        if progress.get("synthesized"):
            return

        def finish(message, **values):
            repo.heartbeat_research(
                leased, {"stage": "complete", "message": message, "synthesized": True, **values}
            )

        repo.heartbeat_research(
            leased, {"stage": "synthesize", "message": "Writing the session synthesis"}
        )
        snapshot = repo.get_session_snapshot(session.id)
        claims = [c for c in snapshot.claims if c.paper_id]
        papers = {p.paper.id: p.paper for p in snapshot.papers}
        if self.model is None or len({c.paper_id for c in claims}) < 2:
            reason = (
                "Session synthesis needs a configured research model."
                if self.model is None
                else "Fewer than two papers produced claims, so no cross-paper synthesis was written."
            )
            repo.record_research_decision(
                leased,
                skipped_synthesis(leased, reason),
                max_branches=limits.max_branches,
            )
            finish(reason)
            return
        model = BudgetedModel(self.model, repo, leased, limits, root=True)
        aliases, data = synthesis_input(session, snapshot.branches, claims, papers)
        try:
            synthesis, provenance = await model.generate(
                SessionSynthesis, SYNTHESIS_INSTRUCTION, data, priority=True
            )
        except (ModelUnavailable, ValueError) as exc:
            reason = (
                f"{exc}; no session synthesis was written."
                if isinstance(exc, ModelUnavailable)
                else "The model's synthesis was invalid, so none was saved."
            )
            repo.record_research_decision(
                leased, skipped_synthesis(leased, reason), max_branches=limits.max_branches
            )
            finish(reason)
            return
        hypotheses, decision = accept_synthesis(
            synthesis,
            leased=leased,
            session=session,
            aliases=aliases,
            provenance=provenance,
        )
        repo.save_session_synthesis(
            leased,
            SynthesisRecord(
                summary_id=stable_id(session.id, "session-synthesis"),
                overview=synthesis.overview,
                provenance=provenance,
                hypotheses=hypotheses,
                decision=decision,
            ),
        )
        finish(
            f"Synthesis written with {len(hypotheses)} cross-paper hypothes"
            + ("is" if len(hypotheses) == 1 else "es")
        )
