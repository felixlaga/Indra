"""Dynamic query planning for research searches.

Creates structured search strategies before executing searches,
helping the agent make informed decisions about how to approach
a research question.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.protocols import LLMProvider

logger = logging.getLogger(__name__)


class DiversityDimension(str, Enum):
    """Dimensions along which to seek diversity in search results."""

    METHODOLOGY = "methodology"
    APPLICATION_DOMAIN = "application_domain"
    AUTHOR_BACKGROUND = "author_background"
    PUBLICATION_VENUE = "publication_venue"
    GEOGRAPHIC_REGION = "geographic_region"
    THEORETICAL_FRAMEWORK = "theoretical_framework"


class SaturationCriterion(str, Enum):
    """Criteria for determining when to stop searching."""

    NO_NEW_CONCEPTS = "no_new_concepts"
    CITATION_OVERLAP = "citation_overlap"
    DIMINISHING_RELEVANCE = "diminishing_relevance"
    TARGET_COUNT_REACHED = "target_count_reached"
    TIME_LIMIT = "time_limit"


@dataclass
class SearchPlan:
    """
    A structured search strategy plan for a research question.

    Contains the key elements needed to execute an effective
    and comprehensive literature search.
    """

    # Core search parameters
    key_concepts: list[str]
    """Key concepts and terms to search for."""

    time_range_start: str | None
    """Start of relevant time range (e.g., '2020', '2020-01')."""

    time_range_end: str | None
    """End of relevant time range (e.g., '2024', '2024-12')."""

    initial_paper_target: int
    """Target number of papers to find initially."""

    # Diversity parameters
    diversity_dimensions: list[DiversityDimension]
    """Dimensions along which to seek diversity."""

    # Stopping criteria
    saturation_criteria: list[SaturationCriterion]
    """Criteria for when to stop searching."""

    saturation_threshold: float = 0.8
    """Threshold for saturation (e.g., 80% overlap in citations)."""

    # Additional context
    search_rationale: str = ""
    """Explanation of why this search strategy was chosen."""

    alternative_queries: list[str] = field(default_factory=list)
    """Alternative query formulations to try."""

    exclusion_terms: list[str] = field(default_factory=list)
    """Terms to exclude from search results."""

    required_fields_of_study: list[str] = field(default_factory=list)
    """Fields of study that papers should belong to."""

    def to_dict(self) -> dict:
        """Convert plan to dictionary for serialization."""
        return {
            "key_concepts": self.key_concepts,
            "time_range": {
                "start": self.time_range_start,
                "end": self.time_range_end,
            },
            "initial_paper_target": self.initial_paper_target,
            "diversity_dimensions": [d.value for d in self.diversity_dimensions],
            "saturation_criteria": [c.value for c in self.saturation_criteria],
            "saturation_threshold": self.saturation_threshold,
            "search_rationale": self.search_rationale,
            "alternative_queries": self.alternative_queries,
            "exclusion_terms": self.exclusion_terms,
            "required_fields_of_study": self.required_fields_of_study,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SearchPlan:
        """Create a SearchPlan from a dictionary."""
        time_range = data.get("time_range", {})

        # Parse diversity dimensions
        diversity_dims = []
        for dim in data.get("diversity_dimensions", []):
            try:
                diversity_dims.append(DiversityDimension(dim))
            except ValueError:
                logger.warning(f"Unknown diversity dimension: {dim}")

        # Parse saturation criteria
        sat_criteria = []
        for criterion in data.get("saturation_criteria", []):
            try:
                sat_criteria.append(SaturationCriterion(criterion))
            except ValueError:
                logger.warning(f"Unknown saturation criterion: {criterion}")

        return cls(
            key_concepts=data.get("key_concepts", []),
            time_range_start=time_range.get("start"),
            time_range_end=time_range.get("end"),
            initial_paper_target=data.get("initial_paper_target", 20),
            diversity_dimensions=diversity_dims,
            saturation_criteria=sat_criteria,
            saturation_threshold=data.get("saturation_threshold", 0.8),
            search_rationale=data.get("search_rationale", ""),
            alternative_queries=data.get("alternative_queries", []),
            exclusion_terms=data.get("exclusion_terms", []),
            required_fields_of_study=data.get("required_fields_of_study", []),
        )


QUERY_PLANNER_SYSTEM_PROMPT = """You are a research query planning assistant. Your task is to analyze research questions and create comprehensive search strategies.

You should:
- Identify the key concepts and terminology relevant to the research question
- Determine appropriate time ranges based on when relevant work was likely published
- Suggest a reasonable initial paper target based on the scope of the question
- Identify which diversity dimensions matter for a comprehensive literature review
- Define clear stopping criteria to avoid infinite searches

Output your plan as a JSON object with the following structure:
{
    "key_concepts": ["concept1", "concept2", ...],
    "time_range": {
        "start": "YYYY" or "YYYY-MM" or null,
        "end": "YYYY" or "YYYY-MM" or null
    },
    "initial_paper_target": <integer>,
    "diversity_dimensions": ["methodology", "application_domain", "author_background", "publication_venue", "geographic_region", "theoretical_framework"],
    "saturation_criteria": ["no_new_concepts", "citation_overlap", "diminishing_relevance", "target_count_reached", "time_limit"],
    "saturation_threshold": <float 0-1>,
    "search_rationale": "explanation of strategy",
    "alternative_queries": ["query1", "query2", ...],
    "exclusion_terms": ["term1", "term2", ...],
    "required_fields_of_study": ["field1", "field2", ...]
}"""

QUERY_PLANNER_PROMPT_TEMPLATE = """Given research question: {query}

Create a search strategy by answering these questions:
1. What are the key concepts to search for?
2. What time range is relevant?
3. How many papers should we aim for initially?
4. What diversity dimensions matter? (methodology, application domain, author background, publication venue, geographic region, theoretical framework)
5. When should we stop searching? (no new concepts, citation overlap, diminishing relevance, target count reached, time limit)

Consider:
- The breadth and depth of the research question
- Whether this is an emerging field or established area
- What types of papers would be most valuable
- How to ensure comprehensive coverage without over-searching

Output your plan as structured JSON."""


class QueryPlanner:
    """
    Creates dynamic search strategies for research questions.

    The planner uses an LLM to analyze research questions and
    generate structured search plans that guide the search process.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        temperature: float = 0.3,
        default_paper_target: int = 20,
    ):
        """
        Initialize the query planner.

        Args:
            llm_provider: LLM provider for plan generation. If None,
                         uses the default OpenRouterAdapter.
            temperature: LLM temperature (lower = more focused)
            default_paper_target: Default paper target if not specified in plan
        """
        self._llm_provider = llm_provider
        self.temperature = temperature
        self.default_paper_target = default_paper_target

    async def create_plan(
        self,
        query: str,
        context: str | None = None,
    ) -> SearchPlan:
        """
        Create a search plan for a research question.

        Args:
            query: The research question to plan for
            context: Optional additional context about the research goals

        Returns:
            A structured SearchPlan

        Raises:
            ValueError: If the plan cannot be parsed
        """
        prompt = QUERY_PLANNER_PROMPT_TEMPLATE.format(query=query)

        if context:
            prompt += f"\n\nAdditional context: {context}"

        # Use provided provider or create a temporary one
        if self._llm_provider is not None:
            # Use provided provider directly (caller manages lifecycle)
            response = await self._llm_provider.complete(
                prompt=prompt,
                system_prompt=QUERY_PLANNER_SYSTEM_PROMPT,
                temperature=self.temperature,
            )
        else:
            # Create and manage our own provider
            from ..llm.adapters import OpenRouterAdapter

            async with OpenRouterAdapter() as provider:
                response = await provider.complete(
                    prompt=prompt,
                    system_prompt=QUERY_PLANNER_SYSTEM_PROMPT,
                    temperature=self.temperature,
                )

        plan = self._parse_response(response)
        logger.info(
            f"Created search plan with {len(plan.key_concepts)} key concepts, "
            f"target {plan.initial_paper_target} papers"
        )
        return plan

    def _parse_response(self, response: str) -> SearchPlan:
        """
        Parse the LLM response into a SearchPlan.

        Args:
            response: The raw LLM response

        Returns:
            A validated SearchPlan

        Raises:
            ValueError: If the response cannot be parsed
        """
        # Try to extract JSON from the response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1

        if json_start == -1 or json_end <= json_start:
            logger.error("No JSON object found in response")
            raise ValueError("Failed to parse query plan: no JSON found")

        json_str = response[json_start:json_end]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise ValueError(f"Failed to parse query plan JSON: {e}")

        # Validate required fields
        self._validate_plan_data(data)

        return SearchPlan.from_dict(data)

    def _validate_plan_data(self, data: dict) -> None:
        """
        Validate the parsed plan data.

        Args:
            data: The parsed JSON data

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Check for key_concepts
        if "key_concepts" not in data or not data["key_concepts"]:
            raise ValueError("Search plan must include at least one key concept")

        if not isinstance(data["key_concepts"], list):
            raise ValueError("key_concepts must be a list")

        # Validate initial_paper_target
        if "initial_paper_target" in data:
            target = data["initial_paper_target"]
            if not isinstance(target, int) or target < 1:
                logger.warning(
                    f"Invalid paper target {target}, using default {self.default_paper_target}"
                )
                data["initial_paper_target"] = self.default_paper_target
        else:
            data["initial_paper_target"] = self.default_paper_target

        # Validate saturation_threshold
        if "saturation_threshold" in data:
            threshold = data["saturation_threshold"]
            if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
                logger.warning(f"Invalid saturation threshold {threshold}, using 0.8")
                data["saturation_threshold"] = 0.8

        # Ensure diversity_dimensions is a list
        if "diversity_dimensions" not in data:
            data["diversity_dimensions"] = []
        elif not isinstance(data["diversity_dimensions"], list):
            data["diversity_dimensions"] = []

        # Ensure saturation_criteria is a list
        if "saturation_criteria" not in data:
            data["saturation_criteria"] = [SaturationCriterion.TARGET_COUNT_REACHED.value]
        elif not isinstance(data["saturation_criteria"], list):
            data["saturation_criteria"] = [SaturationCriterion.TARGET_COUNT_REACHED.value]

    def create_default_plan(self, query: str) -> SearchPlan:
        """
        Create a default search plan without LLM.

        Useful as a fallback or for simple queries.

        Args:
            query: The research question

        Returns:
            A basic SearchPlan with sensible defaults
        """
        # Extract simple key concepts from the query
        # Remove common words and split by whitespace
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "and", "but", "if", "or", "because",
            "until", "while", "what", "which", "who", "whom", "this",
            "that", "these", "those", "am", "about",
        }

        words = query.lower().split()
        key_concepts = [
            word.strip("?.,!\"'")
            for word in words
            if word.strip("?.,!\"'") not in stop_words and len(word) > 2
        ]

        # Deduplicate while preserving order
        seen = set()
        unique_concepts = []
        for concept in key_concepts:
            if concept not in seen:
                seen.add(concept)
                unique_concepts.append(concept)

        return SearchPlan(
            key_concepts=unique_concepts[:10],  # Limit to 10 concepts
            time_range_start=None,
            time_range_end=None,
            initial_paper_target=self.default_paper_target,
            diversity_dimensions=[
                DiversityDimension.METHODOLOGY,
                DiversityDimension.APPLICATION_DOMAIN,
            ],
            saturation_criteria=[
                SaturationCriterion.TARGET_COUNT_REACHED,
                SaturationCriterion.NO_NEW_CONCEPTS,
            ],
            saturation_threshold=0.8,
            search_rationale="Default plan generated from query keywords",
            alternative_queries=[],
            exclusion_terms=[],
            required_fields_of_study=[],
        )


async def create_search_plan(
    query: str,
    context: str | None = None,
    provider: LLMProvider | None = None,
) -> SearchPlan:
    """
    Convenience function to create a search plan.

    Args:
        query: The research question to plan for
        context: Optional additional context
        provider: Optional LLM provider

    Returns:
        A structured SearchPlan

    Example:
        plan = await create_search_plan(
            "What are the applications of transformer models in healthcare?"
        )
    """
    planner = QueryPlanner(llm_provider=provider)
    return await planner.create_plan(query=query, context=context)
