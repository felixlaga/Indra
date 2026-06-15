"""
Reflection Loop: Post-summarization evaluation and gap identification.

Phase 5 of the recursive research agent system.
Evaluates paper selections after summarization to identify gaps
and optionally trigger additional searches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config.loader import ReflectionConfig
    from ..llm.protocols import LLMProvider
    from ..semantic_scholar import SemanticScholarAdapter, SearchFilters
    from .models import Branch, ValidatedSummary

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """Result of a reflection evaluation."""

    branch_id: str
    coverage_score: float  # 0-1 score for topic breadth coverage
    identified_gaps: list[str]  # Research areas that are underexplored
    low_value_papers: list[str]  # Paper IDs that were less useful than expected
    suggested_searches: list[str]  # New search queries to fill gaps
    should_search_more: bool  # Whether additional searches are recommended
    reasoning: str  # Explanation of the evaluation
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def no_gaps(cls, branch_id: str, reasoning: str = "Coverage appears complete") -> ReflectionResult:
        """Create a result indicating no gaps found."""
        return cls(
            branch_id=branch_id,
            coverage_score=1.0,
            identified_gaps=[],
            low_value_papers=[],
            suggested_searches=[],
            should_search_more=False,
            reasoning=reasoning,
        )


# Tool definition for Claude-based reflection
REFLECT_ON_PAPERS_TOOL = {
    "name": "reflect_on_papers",
    "description": """Reflect on the papers that have been selected and summarized.

Evaluate:
1. Did you cover the breadth of the topic?
2. Are there obvious gaps in the research coverage?
3. Were some papers less useful than expected?
4. Should you search for more papers in a specific area?

Provide a detailed assessment with actionable recommendations.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "coverage_score": {
                "type": "number",
                "description": "Score from 0-1 indicating how well the topic breadth is covered",
                "minimum": 0,
                "maximum": 1,
            },
            "identified_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of research areas or subtopics that are underexplored",
            },
            "low_value_papers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paper IDs that were less useful than expected (tangential, low quality, etc.)",
            },
            "suggested_searches": {
                "type": "array",
                "items": {"type": "string"},
                "description": "New search queries to fill identified gaps",
            },
            "should_search_more": {
                "type": "boolean",
                "description": "Whether additional searches are recommended to improve coverage",
            },
            "reasoning": {
                "type": "string",
                "description": "Detailed explanation of the evaluation and recommendations",
            },
        },
        "required": ["coverage_score", "should_search_more", "reasoning"],
    },
}


class ReflectionAgent:
    """
    Reflection agent for post-summarization evaluation.

    Evaluates the papers selected and summarized to:
    - Assess topic coverage breadth
    - Identify research gaps
    - Flag low-value papers
    - Recommend additional searches
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        search_provider: SemanticScholarAdapter | None = None,
        config: ReflectionConfig | None = None,
    ):
        """
        Initialize the reflection agent.

        Args:
            llm_provider: LLM provider for reflection reasoning
            search_provider: Optional search provider for gap-filling searches
            config: Reflection configuration
        """
        self.llm = llm_provider
        self.search_provider = search_provider

        if config is None:
            from ..config.loader import ReflectionConfig
            config = ReflectionConfig()

        self.config = config
        self.min_papers_for_reflection = config.min_papers_for_reflection
        self.auto_search_gaps = config.auto_search_gaps
        self.max_gap_searches = config.max_gap_searches
        self.coverage_threshold = config.coverage_threshold

    def should_reflect(self, branch: Branch) -> bool:
        """
        Check if a branch should undergo reflection.

        Args:
            branch: Branch to check

        Returns:
            True if reflection should occur
        """
        return len(branch.accumulated_summaries) >= self.min_papers_for_reflection

    async def reflect(
        self,
        branch: Branch,
        research_query: str | None = None,
    ) -> ReflectionResult:
        """
        Perform reflection on a branch's paper selections.

        Args:
            branch: Branch to reflect on
            research_query: Optional original research query for context

        Returns:
            ReflectionResult with evaluation and recommendations
        """
        if not self.should_reflect(branch):
            logger.info(
                f"Skipping reflection for branch {branch.id}: "
                f"not enough papers ({len(branch.accumulated_summaries)} < {self.min_papers_for_reflection})"
            )
            return ReflectionResult.no_gaps(
                branch.id,
                f"Not enough papers for reflection (need {self.min_papers_for_reflection})",
            )

        logger.info(f"Reflecting on branch {branch.id} with {len(branch.accumulated_summaries)} papers")

        # Build context from summaries
        summaries_text = self._format_summaries(branch)

        # Build the reflection prompt
        prompt = self._build_reflection_prompt(
            summaries_text=summaries_text,
            query=research_query or branch.query,
            paper_count=len(branch.accumulated_summaries),
        )

        try:
            # Check if LLM supports tool use
            if hasattr(self.llm, 'complete_with_tools'):
                response = await self.llm.complete_with_tools(
                    prompt=prompt,
                    tools=[REFLECT_ON_PAPERS_TOOL],
                    system_prompt=self._get_system_prompt(),
                    temperature=0.4,
                    max_tokens=2048,
                )

                if response.get("tool_use"):
                    return self._parse_tool_response(response["tool_use"][0], branch.id)

            # Fallback to simple completion
            response_text = await self.llm.complete(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                temperature=0.4,
                max_tokens=2048,
            )
            return self._parse_text_response(response_text, branch.id)

        except Exception as e:
            logger.error(f"Error during reflection for branch {branch.id}: {e}")
            return ReflectionResult.no_gaps(branch.id, f"Reflection failed: {e}")

    def _format_summaries(self, branch: Branch) -> str:
        """Format summaries for the reflection prompt."""
        lines = []
        for paper_id, summary in branch.accumulated_summaries.items():
            paper = branch.accumulated_papers.get(paper_id)
            title = paper.title if paper else summary.paper_title
            year = paper.year if paper else "N/A"
            fields = ", ".join((paper.fields_of_study or [])[:3]) if paper else "N/A"

            lines.append(
                f"[{paper_id}] {title} ({year})\n"
                f"  Fields: {fields}\n"
                f"  Groundedness: {summary.groundedness:.0%}\n"
                f"  Summary: {summary.summary[:300]}..."
            )

        return "\n\n".join(lines)

    def _build_reflection_prompt(
        self,
        summaries_text: str,
        query: str,
        paper_count: int,
    ) -> str:
        """Build the reflection prompt."""
        return f"""Review the papers you selected and summarized for the research query.

## Original Research Query
"{query}"

## Papers Selected and Summarized ({paper_count} papers)
{summaries_text}

## Reflection Questions
Please reflect on your paper selections:

1. Did you cover the breadth of the topic?
   - Are multiple perspectives and approaches represented?
   - Is there a good mix of foundational and recent work?

2. Are there obvious gaps?
   - What important subtopics or approaches are missing?
   - Are there relevant fields or methodologies not represented?

3. Were some papers less useful than expected?
   - Which papers were tangential to the main research question?
   - Were any papers of lower quality or relevance?

4. Should you search for more papers in a specific area?
   - What additional searches would improve coverage?
   - What keywords or topics should be explored?

Use the reflect_on_papers tool to provide your detailed assessment."""

    def _get_system_prompt(self) -> str:
        """Get the system prompt for reflection."""
        return """You are an expert research analyst evaluating the quality and coverage of a literature review.

Your role is to:
- Assess how well the selected papers cover the research topic
- Identify gaps in coverage that should be filled
- Flag papers that may be less relevant than initially expected
- Suggest specific searches to improve the literature review

Be thorough but practical. Not every gap needs to be filled - focus on significant omissions
that would materially improve the research understanding.

Always use the reflect_on_papers tool to provide your structured assessment."""

    def _parse_tool_response(self, tool_call: dict, branch_id: str) -> ReflectionResult:
        """Parse the tool call response into a ReflectionResult."""
        try:
            input_data = tool_call.get("input", {})

            return ReflectionResult(
                branch_id=branch_id,
                coverage_score=input_data.get("coverage_score", 0.5),
                identified_gaps=input_data.get("identified_gaps", []),
                low_value_papers=input_data.get("low_value_papers", []),
                suggested_searches=input_data.get("suggested_searches", []),
                should_search_more=input_data.get("should_search_more", False),
                reasoning=input_data.get("reasoning", "No reasoning provided"),
            )

        except Exception as e:
            logger.error(f"Error parsing reflection tool response: {e}")
            return ReflectionResult.no_gaps(branch_id, f"Parse error: {e}")

    def _parse_text_response(self, response: str, branch_id: str) -> ReflectionResult:
        """Parse a plain text response into a ReflectionResult (fallback)."""
        # Simple heuristic parsing for non-tool-use models
        should_search = any(
            phrase in response.lower()
            for phrase in ["should search", "recommend searching", "gap", "missing", "additional papers"]
        )

        # Extract suggested searches (look for quoted strings or bullet points)
        import re
        searches = re.findall(r'"([^"]+)"|\'([^\']+)\'', response)
        suggested = [s[0] or s[1] for s in searches if s[0] or s[1]][:5]

        # Estimate coverage based on sentiment
        coverage = 0.7 if should_search else 0.9

        return ReflectionResult(
            branch_id=branch_id,
            coverage_score=coverage,
            identified_gaps=[],  # Can't reliably extract from plain text
            low_value_papers=[],
            suggested_searches=suggested,
            should_search_more=should_search,
            reasoning=response[:500],
        )

    async def fill_gaps(
        self,
        branch: Branch,
        reflection_result: ReflectionResult,
        filters: SearchFilters | None = None,
    ) -> list[Any]:
        """
        Execute gap-filling searches based on reflection results.

        Args:
            branch: Branch to add papers to
            reflection_result: Result from reflection evaluation
            filters: Optional search filters

        Returns:
            List of papers found from gap-filling searches
        """
        if not self.search_provider:
            logger.warning("No search provider configured for gap filling")
            return []

        if not reflection_result.should_search_more:
            logger.info("Reflection indicates no gap filling needed")
            return []

        if not reflection_result.suggested_searches:
            logger.info("No specific searches suggested")
            return []

        all_papers = []
        searches_to_run = reflection_result.suggested_searches[:self.max_gap_searches]

        logger.info(f"Running {len(searches_to_run)} gap-filling searches")

        for search_query in searches_to_run:
            try:
                papers = await self.search_provider.search_papers(
                    query=search_query,
                    filters=filters,
                    limit=10,  # Smaller limit for gap filling
                )

                # Filter out papers we already have
                new_papers = [
                    p for p in papers
                    if p.paper_id not in branch.accumulated_papers
                ]

                all_papers.extend(new_papers)
                logger.info(f"Gap search '{search_query}': found {len(new_papers)} new papers")

            except Exception as e:
                logger.warning(f"Error in gap-filling search '{search_query}': {e}")

        return all_papers


async def create_reflection_agent(
    llm_provider: LLMProvider,
    search_provider: SemanticScholarAdapter | None = None,
    config: ReflectionConfig | None = None,
) -> ReflectionAgent:
    """
    Factory function to create a ReflectionAgent.

    Args:
        llm_provider: LLM provider for reflection reasoning
        search_provider: Optional search provider for gap filling
        config: Reflection configuration

    Returns:
        Configured ReflectionAgent instance
    """
    return ReflectionAgent(
        llm_provider=llm_provider,
        search_provider=search_provider,
        config=config,
    )
