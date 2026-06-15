"""Hypothesis generation from validated summaries."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.protocols import LLMProvider
    from ..orchestration.models import ValidatedSummary, ResearchHypothesis

logger = logging.getLogger(__name__)

HYPOTHESIS_SYSTEM_PROMPT = """You are a research hypothesis generator. Your task is to analyze research paper summaries and generate novel, testable research hypotheses.

Guidelines:
- Generate hypotheses that bridge findings across multiple papers
- Focus on gaps in current research that could be explored
- Ensure hypotheses are specific, testable, and grounded in the provided evidence
- Each hypothesis should cite which papers support it
- Rate your confidence (0-1) based on how well-supported the hypothesis is

Output format: JSON array of hypotheses, each with:
- "text": The hypothesis statement (a research question or testable claim)
- "supporting_papers": List of paper titles that support this hypothesis
- "confidence": Float 0-1 indicating confidence
- "rationale": Brief explanation of why this is a promising research direction"""


HYPOTHESIS_PROMPT_TEMPLATE = """Based on the following research paper summaries, generate {num_hypotheses} novel research hypotheses.

{context}

Paper Summaries:
{summaries}

Generate {num_hypotheses} hypotheses that:
1. Identify gaps or unexplored connections in the research
2. Are testable and specific
3. Build on findings from multiple papers
4. Could lead to impactful research

Return ONLY a JSON array of hypothesis objects."""


class HypothesisGenerator:
    """
    Generates research hypotheses from validated summaries using LLM.

    The generator analyzes patterns across multiple paper summaries
    to identify research gaps and generate novel hypotheses.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        hypotheses_per_batch: int = 3,
        temperature: float = 0.7,
    ):
        """
        Initialize the hypothesis generator.

        Args:
            llm_provider: LLM provider for generation
            hypotheses_per_batch: Number of hypotheses to generate per call
            temperature: LLM temperature (higher = more creative)
        """
        self.llm = llm_provider
        self.hypotheses_per_batch = hypotheses_per_batch
        self.temperature = temperature

    async def generate(
        self,
        summaries: list[ValidatedSummary],
        branch_id: str,
        context: str | None = None,
        num_hypotheses: int | None = None,
    ) -> list[ResearchHypothesis]:
        """
        Generate research hypotheses from validated summaries.

        Args:
            summaries: List of validated summaries to analyze
            branch_id: ID of the branch these hypotheses belong to
            context: Optional additional context (e.g., research goals)
            num_hypotheses: Number of hypotheses to generate

        Returns:
            List of generated research hypotheses
        """
        from ..orchestration.models import ResearchHypothesis

        if not summaries:
            logger.warning("No summaries provided for hypothesis generation")
            return []

        num_hypotheses = num_hypotheses or self.hypotheses_per_batch

        # Format summaries for the prompt
        summary_texts = []
        paper_id_map = {}  # Map title to paper_id

        for i, s in enumerate(summaries, 1):
            summary_texts.append(
                f"Paper {i}: {s.paper_title}\n"
                f"Groundedness: {s.groundedness:.2%}\n"
                f"Summary: {s.summary}\n"
            )
            paper_id_map[s.paper_title] = s.paper_id

        summaries_str = "\n---\n".join(summary_texts)
        context_str = f"\nResearch Context: {context}\n" if context else ""

        prompt = HYPOTHESIS_PROMPT_TEMPLATE.format(
            num_hypotheses=num_hypotheses,
            context=context_str,
            summaries=summaries_str,
        )

        try:
            response = await self.llm.complete(
                prompt=prompt,
                system_prompt=HYPOTHESIS_SYSTEM_PROMPT,
                temperature=self.temperature,
            )

            hypotheses = self._parse_response(response, paper_id_map, branch_id)
            logger.info(f"Generated {len(hypotheses)} hypotheses from {len(summaries)} summaries")
            return hypotheses

        except Exception as e:
            logger.error(f"Failed to generate hypotheses: {e}")
            return []

    def _parse_response(
        self,
        response: str,
        paper_id_map: dict[str, str],
        branch_id: str,
    ) -> list[ResearchHypothesis]:
        """Parse LLM response into hypothesis objects."""
        from ..orchestration.models import ResearchHypothesis

        hypotheses = []

        try:
            # Try to extract JSON from response
            # Handle cases where LLM includes extra text
            json_start = response.find("[")
            json_end = response.rfind("]") + 1

            if json_start == -1 or json_end <= json_start:
                logger.warning("No JSON array found in response")
                return []

            json_str = response[json_start:json_end]
            data = json.loads(json_str)

            for item in data:
                if not isinstance(item, dict):
                    continue

                text = item.get("text", "")
                if not text:
                    continue

                # Map paper titles to IDs
                supporting_titles = item.get("supporting_papers", [])
                supporting_ids = []
                for title in supporting_titles:
                    if title in paper_id_map:
                        supporting_ids.append(paper_id_map[title])
                    else:
                        # Try fuzzy matching
                        for stored_title, paper_id in paper_id_map.items():
                            if title.lower() in stored_title.lower() or stored_title.lower() in title.lower():
                                supporting_ids.append(paper_id)
                                break

                confidence = float(item.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

                hypothesis = ResearchHypothesis(
                    id=str(uuid.uuid4()),
                    text=text,
                    supporting_paper_ids=supporting_ids,
                    confidence=confidence,
                    generated_from_branch=branch_id,
                    timestamp=datetime.now(),
                )
                hypotheses.append(hypothesis)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse hypothesis JSON: {e}")
        except Exception as e:
            logger.error(f"Error parsing hypotheses: {e}")

        return hypotheses

    async def generate_from_batch(
        self,
        summaries: list[ValidatedSummary],
        branch_id: str,
        batch_size: int = 10,
        context: str | None = None,
    ) -> list[ResearchHypothesis]:
        """
        Generate hypotheses from summaries in batches.

        Useful when you have many summaries and want to generate
        hypotheses from different subsets.

        Args:
            summaries: All summaries to process
            branch_id: Branch ID for the hypotheses
            batch_size: Number of summaries per batch
            context: Optional research context

        Returns:
            All generated hypotheses
        """
        all_hypotheses = []

        for i in range(0, len(summaries), batch_size):
            batch = summaries[i : i + batch_size]
            hypotheses = await self.generate(
                summaries=batch,
                branch_id=branch_id,
                context=context,
            )
            all_hypotheses.extend(hypotheses)

        return all_hypotheses

    async def refine_hypothesis(
        self,
        hypothesis: ResearchHypothesis,
        feedback: str,
        summaries: list[ValidatedSummary],
    ) -> ResearchHypothesis:
        """
        Refine a hypothesis based on feedback.

        Args:
            hypothesis: Original hypothesis to refine
            feedback: Feedback on how to improve the hypothesis
            summaries: Supporting summaries for context

        Returns:
            Refined hypothesis
        """
        from ..orchestration.models import ResearchHypothesis

        prompt = f"""Refine the following research hypothesis based on the feedback provided.

Original Hypothesis: {hypothesis.text}

Feedback: {feedback}

Supporting Evidence:
{chr(10).join(f"- {s.paper_title}: {s.summary}" for s in summaries[:5])}

Provide a refined hypothesis that addresses the feedback while remaining grounded in the evidence.
Return ONLY a JSON object with: "text", "confidence", "rationale"
"""

        try:
            response = await self.llm.complete(
                prompt=prompt,
                system_prompt=HYPOTHESIS_SYSTEM_PROMPT,
                temperature=0.5,  # Lower temperature for refinement
            )

            # Parse response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])

                return ResearchHypothesis(
                    id=str(uuid.uuid4()),
                    text=data.get("text", hypothesis.text),
                    supporting_paper_ids=hypothesis.supporting_paper_ids,
                    confidence=float(data.get("confidence", hypothesis.confidence)),
                    generated_from_branch=hypothesis.generated_from_branch,
                    timestamp=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Failed to refine hypothesis: {e}")

        return hypothesis  # Return original if refinement fails
