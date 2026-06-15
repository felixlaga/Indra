"""
Managing Agent: Intelligent branch splitting with an OpenRouter-hosted model.

The Managing Agent uses tool calling to make autonomous
decisions about when and how to split research branches based on paper content,
rather than simple context window thresholds.

Key features:
- Autonomous decision-making: Agent decides WHEN and HOW to split
- Flexible split criteria: by topic, methodology, time period, or custom
- Dynamic branch counts: Agent chooses optimal number of sub-branches
- Soft guardrails: Warnings at 70%, recommendations (not forced) at 80%+
- Full reasoning transparency: Every decision comes with explanation
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config.loader import ManagingAgentConfig
    from ..llm.adapters import OpenRouterAdapter
    from .models import Branch

logger = logging.getLogger(__name__)


class BranchAction(Enum):
    """Actions the managing agent can recommend."""

    CONTINUE = "continue"  # Keep exploring this branch
    SPLIT = "split"  # Split into sub-branches
    WRAP_UP = "wrap_up"  # Finish this branch, synthesize findings


class SplitCriteria(Enum):
    """Criteria for splitting branches."""

    BY_TOPIC = "by_topic"  # Group by research themes
    BY_METHODOLOGY = "by_methodology"  # Group by research methods
    BY_TIME_PERIOD = "by_time_period"  # Group by publication era
    BY_APPLICATION = "by_application"  # Group by application domain
    BY_THEORETICAL_FRAMEWORK = "by_theoretical_framework"  # Group by theory used
    BY_DATA_TYPE = "by_data_type"  # Group by data/datasets used
    CUSTOM = "custom"  # Agent-defined custom grouping


@dataclass
class SplitRecommendation:
    """Recommendation from the managing agent about branch splitting."""

    should_split: bool
    action: BranchAction  # The recommended action
    num_branches: int
    paper_groups: list[list[str]]  # Paper IDs grouped for each new branch
    group_queries: list[str]  # Search queries for each group
    group_labels: list[str]  # Human-readable labels for each group
    split_criteria: SplitCriteria | None  # How the split was made
    reasoning: str  # Detailed explanation of the decision
    context_warning: str | None = None  # Warning if context is getting high

    @classmethod
    def continue_exploring(cls, reasoning: str, context_warning: str | None = None) -> SplitRecommendation:
        """Create a recommendation to continue exploring."""
        return cls(
            should_split=False,
            action=BranchAction.CONTINUE,
            num_branches=0,
            paper_groups=[],
            group_queries=[],
            group_labels=[],
            split_criteria=None,
            reasoning=reasoning,
            context_warning=context_warning,
        )

    @classmethod
    def wrap_up(cls, reasoning: str) -> SplitRecommendation:
        """Create a recommendation to wrap up and synthesize."""
        return cls(
            should_split=False,
            action=BranchAction.WRAP_UP,
            num_branches=0,
            paper_groups=[],
            group_queries=[],
            group_labels=[],
            split_criteria=None,
            reasoning=reasoning,
        )

    @classmethod
    def no_split(cls, reasoning: str = "Splitting not recommended") -> SplitRecommendation:
        """Create a recommendation to not split (deprecated, use continue_exploring)."""
        return cls.continue_exploring(reasoning)


# Tool definitions for OpenRouter model - Enhanced with clustering and context tools
CLUSTER_PAPERS_TOOL = {
    "name": "cluster_papers",
    "description": """Group the papers in this branch by a specified criterion.

Use this to understand how papers relate to each other before deciding on splits.
Returns clusters of paper IDs with labels.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "criterion": {
                "type": "string",
                "enum": ["topic", "methodology", "time_period", "application", "citation_network"],
                "description": "How to cluster the papers",
            },
        },
        "required": ["criterion"],
    },
}

GET_BRANCH_CONTEXT_TOOL = {
    "name": "get_branch_context",
    "description": """Get detailed context about what each branch (including siblings) is exploring.

Use this to understand the broader research landscape and avoid overlap when splitting.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "include_siblings": {
                "type": "boolean",
                "description": "Whether to include sibling branches in the context",
                "default": True,
            },
        },
    },
}

MAKE_DECISION_TOOL = {
    "name": "make_branch_decision",
    "description": """Make a decision about this research branch.

After analyzing the papers and context, use this tool to decide what to do next.

You MUST choose one action:
- "continue": Keep exploring this branch as-is
- "split": Divide into sub-branches for deeper exploration
- "wrap_up": This branch has enough coverage, synthesize and finish

If splitting, you decide:
- How many branches (any number that makes sense, not fixed)
- What criteria to use (topic, methodology, time_period, application, theoretical_framework, data_type, or custom)
- What each sub-branch should focus on
- Which papers go to which branch""",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["continue", "split", "wrap_up"],
                "description": "The action to take for this branch",
            },
            "reasoning": {
                "type": "string",
                "description": "Detailed explanation of why you chose this action. Be specific about what you observed in the papers.",
            },
            "split_config": {
                "type": "object",
                "description": "Configuration for splitting (required if action is 'split')",
                "properties": {
                    "num_branches": {
                        "type": "integer",
                        "description": "Number of sub-branches to create. Choose based on distinct themes, not a fixed number.",
                        "minimum": 2,
                    },
                    "criteria": {
                        "type": "string",
                        "enum": ["by_topic", "by_methodology", "by_time_period", "by_application", "by_theoretical_framework", "by_data_type", "custom"],
                        "description": "How to split the papers",
                    },
                    "custom_criteria_description": {
                        "type": "string",
                        "description": "If using 'custom' criteria, describe the grouping logic",
                    },
                    "branches": {
                        "type": "array",
                        "description": "Details for each new branch",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {
                                    "type": "string",
                                    "description": "Human-readable label for this branch",
                                },
                                "query": {
                                    "type": "string",
                                    "description": "Refined search query for this research direction",
                                },
                                "focus": {
                                    "type": "string",
                                    "description": "What this sub-branch should specifically explore",
                                },
                                "paper_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Paper IDs belonging to this branch",
                                },
                            },
                            "required": ["label", "query", "focus", "paper_ids"],
                        },
                    },
                },
            },
        },
        "required": ["action", "reasoning"],
    },
}


# Soft threshold constants
CONTEXT_WARNING_THRESHOLD = 0.70  # Warn agent at 70%
CONTEXT_HIGH_THRESHOLD = 0.80  # Suggest considering split at 80%
CONTEXT_CRITICAL_THRESHOLD = 0.90  # Strongly recommend action at 90%


class ManagingAgent:
    """
    Intelligent branch management agent using OpenRouter managing model.

    The managing agent analyzes research branch content and makes
    autonomous decisions about when and how to split branches based
    on the actual content rather than simple heuristics.

    Key principles:
    - Agent autonomy: Decisions are made by the agent, not hard-coded rules
    - Soft guardrails: Warnings and suggestions, not forced actions
    - Flexible splitting: Criteria and branch count determined by content
    - Transparent reasoning: Every decision includes explanation
    """

    def __init__(
        self,
        llm_adapter: OpenRouterAdapter,
        config: ManagingAgentConfig | None = None,
    ):
        """
        Initialize the managing agent.

        Args:
            llm_adapter: OpenRouter adapter configured for the managing model
            config: Managing agent configuration
        """
        self.llm = llm_adapter

        if config is None:
            from ..config.loader import ManagingAgentConfig
            config = ManagingAgentConfig()

        self.config = config
        self.min_papers = config.min_papers_before_evaluation
        self.evaluation_interval = config.evaluation_interval

        # Track evaluation history
        self._evaluation_count: dict[str, int] = {}

        # Cache for clustering results (to avoid re-computing)
        self._cluster_cache: dict[str, dict] = {}

    def should_evaluate(self, branch: Branch, force: bool = False) -> bool:
        """
        Check if a branch should be evaluated for splitting.

        Args:
            branch: Branch to check
            force: If True, bypass interval check (used for stall detection)

        Returns:
            True if evaluation should occur
        """
        # Need minimum papers
        if len(branch.accumulated_papers) < self.min_papers:
            return False

        # Force evaluation bypasses interval check
        if force:
            return True

        # Check evaluation interval
        branch_evals = self._evaluation_count.get(branch.id, 0)
        iterations_since_eval = len(branch.iterations) - (branch_evals * self.evaluation_interval)

        return iterations_since_eval >= self.evaluation_interval

    def _get_context_status(self, branch: Branch) -> tuple[str, str | None]:
        """
        Get context utilization status and any warnings.

        Returns:
            Tuple of (status_description, warning_message or None)
        """
        utilization = branch.context_utilization

        if utilization >= CONTEXT_CRITICAL_THRESHOLD:
            return (
                f"CRITICAL ({utilization:.0%})",
                f"Context is at {utilization:.0%} - strongly consider splitting or wrapping up soon"
            )
        elif utilization >= CONTEXT_HIGH_THRESHOLD:
            return (
                f"High ({utilization:.0%})",
                f"Context is at {utilization:.0%} - consider whether splitting would help"
            )
        elif utilization >= CONTEXT_WARNING_THRESHOLD:
            return (
                f"Moderate ({utilization:.0%})",
                f"Context is at {utilization:.0%} - still room to continue but be mindful"
            )
        else:
            return (f"Low ({utilization:.0%})", None)

    async def evaluate_branch(self, branch: Branch, force: bool = False) -> SplitRecommendation | None:
        """
        Evaluate a branch and make an autonomous decision about next steps.

        Uses OpenRouter managing model with tool use to analyze the research content
        and decide whether to continue, split, or wrap up.

        Args:
            branch: Branch to evaluate
            force: If True, force evaluation regardless of interval

        Returns:
            SplitRecommendation with the decision and reasoning
        """
        if not self.should_evaluate(branch, force=force):
            return None

        logger.info(f"Managing agent evaluating branch {branch.id}")

        # Build context from papers and summaries
        context = self._build_evaluation_context(branch)
        context_status, context_warning = self._get_context_status(branch)

        # Create the enhanced prompt
        prompt = self._build_autonomous_prompt(branch, context, context_status, context_warning)

        # Track that we evaluated
        self._evaluation_count[branch.id] = self._evaluation_count.get(branch.id, 0) + 1

        try:
            # Run agentic loop until we get a decision
            tools = [CLUSTER_PAPERS_TOOL, GET_BRANCH_CONTEXT_TOOL, MAKE_DECISION_TOOL]
            messages = [{"role": "user", "content": prompt}]
            max_turns = 5  # Prevent infinite loops

            for turn in range(max_turns):
                # Call OpenRouter managing model with tool use
                response = await self.llm.complete_with_tools_messages(
                    messages=messages,
                    tools=tools,
                    system_prompt=self._get_system_prompt(),
                    temperature=0.3,
                    max_tokens=4096,
                )

                # Check if we got a decision
                if response["tool_use"]:
                    # Check for the decision tool
                    decision_call = None
                    tool_results = []

                    for tool_call in response["tool_use"]:
                        if tool_call["name"] == "make_branch_decision":
                            decision_call = tool_call
                            break
                        else:
                            # Execute the tool and collect result
                            result = self._execute_tool(tool_call, branch)
                            tool_results.append({
                                "tool_use_id": tool_call["id"],
                                "content": result,
                            })

                    if decision_call:
                        return self._parse_decision_response(decision_call, branch, context_warning)

                    # No decision yet - add assistant message and tool results, continue loop
                    if tool_results:
                        # Add the assistant's response (with tool calls) to messages
                        # Convert raw content blocks to serializable format
                        assistant_content = []
                        for block in response["raw_content"]:
                            if block.type == "text":
                                assistant_content.append({
                                    "type": "text",
                                    "text": block.text,
                                })
                            elif block.type == "tool_use":
                                assistant_content.append({
                                    "type": "tool_use",
                                    "id": block.id,
                                    "name": block.name,
                                    "input": block.input,
                                })

                        messages.append({
                            "role": "assistant",
                            "content": assistant_content,
                        })
                        # Add tool results
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "tool_result", **tr} for tr in tool_results
                            ],
                        })
                        logger.debug(f"Managing agent turn {turn + 1}: executed {len(tool_results)} tools, continuing...")
                    else:
                        # No tools executed and no decision - something's wrong
                        logger.warning("Managing agent called tools but none were executable")
                        break

                elif response["stop_reason"] == "end_turn":
                    # Agent finished without using decision tool - extract any text reasoning
                    logger.warning("Managing agent ended turn without making a decision")
                    # Default to continue if no decision was made
                    return SplitRecommendation.continue_exploring(
                        reasoning="Agent did not make explicit decision - defaulting to continue",
                        context_warning=context_warning,
                    )
                else:
                    logger.warning(f"Unexpected response from managing agent: {response['stop_reason']}")
                    break

            # Max turns reached without decision
            logger.warning(f"Managing agent reached max turns ({max_turns}) without decision")
            return SplitRecommendation.continue_exploring(
                reasoning="Agent reached max turns without decision - defaulting to continue",
                context_warning=context_warning,
            )

        except Exception as e:
            logger.error(f"Error evaluating branch with managing agent: {e}")
            return None

    def _execute_tool(self, tool_call: dict, branch: Branch) -> str:
        """
        Execute a tool call and return the result as a string.

        Args:
            tool_call: Tool call dict with 'name' and 'input'
            branch: Current branch for context

        Returns:
            JSON string result of the tool execution
        """
        tool_name = tool_call["name"]
        tool_input = tool_call.get("input", {})

        try:
            if tool_name == "cluster_papers":
                criterion = tool_input.get("criterion", "topic")
                clusters = self._cluster_papers_by_criterion(branch, criterion)
                result = {
                    "criterion": criterion,
                    "clusters": {
                        label: {
                            "paper_ids": paper_ids,
                            "count": len(paper_ids),
                        }
                        for label, paper_ids in clusters.items()
                    },
                    "total_papers": len(branch.accumulated_papers),
                }
                logger.debug(f"Clustered papers by {criterion}: {len(clusters)} clusters")
                return json.dumps(result, indent=2)

            elif tool_name == "get_branch_context":
                # For now, return info about the current branch
                # In a full implementation, this would fetch sibling branch info
                include_siblings = tool_input.get("include_siblings", True)
                context_info = {
                    "current_branch": {
                        "id": branch.id,
                        "query": branch.query,
                        "paper_count": len(branch.accumulated_papers),
                        "summary_count": len(branch.accumulated_summaries),
                        "iteration_count": len(branch.iterations),
                        "mode": branch.mode.value if hasattr(branch.mode, 'value') else str(branch.mode),
                    },
                    "parent_branch_id": branch.parent_branch_id,
                    "siblings": [],  # Would be populated if we had access to sibling branches
                }
                if include_siblings:
                    context_info["note"] = "Sibling branch information not available in current context"
                logger.debug(f"Retrieved branch context for {branch.id}")
                return json.dumps(context_info, indent=2)

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return json.dumps({"error": str(e)})

    def _build_evaluation_context(self, branch: Branch) -> dict[str, Any]:
        """Build context dict from branch papers and summaries."""
        papers_info = []

        # Group papers by field for topic overview
        fields_count: dict[str, int] = {}
        years: list[int] = []

        for paper_id, paper in branch.accumulated_papers.items():
            paper_info = {
                "id": paper_id,
                "title": paper.title,
                "year": paper.year,
                "citation_count": paper.citation_count,
                "fields": paper.fields_of_study or [],
            }

            # Track fields
            for field in (paper.fields_of_study or [])[:3]:
                fields_count[field] = fields_count.get(field, 0) + 1

            # Track years
            if paper.year:
                years.append(paper.year)

            # Add summary if available
            if paper_id in branch.accumulated_summaries:
                summary = branch.accumulated_summaries[paper_id]
                paper_info["summary"] = summary.summary[:500]  # Truncate for context
                paper_info["groundedness"] = summary.groundedness

            papers_info.append(paper_info)

        # Compute topic summary
        sorted_fields = sorted(fields_count.items(), key=lambda x: x[1], reverse=True)
        topic_summary = ", ".join(f"{f} ({c})" for f, c in sorted_fields[:5])

        # Compute time range
        time_range = f"{min(years)}-{max(years)}" if years else "Unknown"

        # Check for stalled state (recent iterations found no new papers)
        recent_iterations = branch.iterations[-3:] if branch.iterations else []
        recent_empty_count = sum(
            1 for it in recent_iterations if not it.papers_found
        )
        is_stalled = recent_empty_count >= 2 and len(branch.iterations) > 1

        return {
            "branch_id": branch.id,
            "query": branch.query,
            "iteration_count": len(branch.iterations),
            "paper_count": len(papers_info),
            "context_utilization": branch.context_utilization,
            "papers": papers_info,
            "topic_summary": topic_summary or "Not enough data",
            "time_range": time_range,
            "parent_branch_id": branch.parent_branch_id,
            "is_stalled": is_stalled,
            "recent_empty_iterations": recent_empty_count,
        }

    def _build_autonomous_prompt(
        self,
        branch: Branch,
        context: dict,
        context_status: str,
        context_warning: str | None,
    ) -> str:
        """Build the enhanced autonomous decision prompt for OpenRouter model."""

        papers_text = "\n".join([
            f"- [{p['id']}] {p['title']} ({p['year']}) - "
            f"Citations: {p['citation_count']}, Fields: {', '.join(p['fields'][:3])}"
            + (f"\n  Summary: {p.get('summary', 'N/A')[:200]}..." if p.get('summary') else "")
            for p in context["papers"]
        ])

        warning_section = ""
        if context_warning:
            warning_section = f"""
## Context Warning
{context_warning}

Note: This is a soft warning, not a forced action. Use your judgment about what's best for the research.
"""

        stall_section = ""
        if context.get("is_stalled"):
            stall_section = f"""
## IMPORTANT: Citation Graph Exhausted
The last {context.get('recent_empty_iterations', 0)} iterations found NO new papers. The citation graph for this query appears to be exhausted.

You should strongly consider:
1. **Wrap up** this branch if you have sufficient coverage for synthesis
2. **Split** into sub-branches with more specific queries to find new papers
3. Only **continue** if you believe there's a specific reason more papers might appear

Do NOT recommend "continue" if papers have stopped appearing - this wastes resources.
"""

        return f"""You are managing a research branch exploring: "{context['query']}"

## Current State
- Papers processed: {context['paper_count']}
- Topics covered: {context['topic_summary']}
- Time range: {context['time_range']}
- Context usage: {context_status}
- Iterations completed: {context['iteration_count']}
- Parent branch: {context['parent_branch_id'] or 'None (root branch)'}
{warning_section}{stall_section}
## Papers in this branch:
{papers_text}

## Your Task

Analyze this research branch and decide what to do next.

You have tools available:
- `cluster_papers`: Group papers by topic, methodology, time period, or application to understand structure
- `get_branch_context`: See what sibling branches are exploring to avoid overlap
- `make_branch_decision`: Make your final decision (REQUIRED)

Consider these questions:
1. Are there distinct research themes or directions emerging?
2. Would splitting help explore different aspects more deeply?
3. Is there enough coherent coverage that we should wrap up and synthesize?
4. Are we duplicating work that other branches might be doing?

## Guidelines for Decisions

**Continue** when:
- Papers are coherent and building toward a clear direction
- More depth is needed in the current direction
- Not enough distinct themes to warrant splitting

**Split** when:
- You identify 2+ distinct themes that would benefit from focused exploration
- Each potential sub-branch has enough papers (3+) to be viable
- The themes are genuinely different (not just variations)
- Choose the number of branches based on what you see, not a fixed number
- Choose criteria that best captures the natural divisions

**Wrap up** when:
- The research direction has been well-covered
- Further exploration would yield diminishing returns
- The branch has produced good coverage for synthesis

Make your decision using the `make_branch_decision` tool. Explain your reasoning clearly."""

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the managing agent."""
        return """You are an expert research strategist managing a literature exploration system.

Your role is to make intelligent, autonomous decisions about research branch management.
You analyze academic papers and decide when research directions should:
- Continue exploring deeper
- Split into focused sub-branches
- Wrap up for synthesis

You have deep expertise in:
- Identifying research themes, methodologies, and application domains
- Recognizing when research directions diverge vs. converge
- Optimizing research exploration strategies for depth and breadth
- Understanding academic paper relationships and citation networks

Decision principles:
1. Be decisive but thoughtful - every decision should have clear reasoning
2. Prefer continuing when uncertain - splitting too early fragments research
3. Split when there's genuine divergence, not just variety
4. Consider the bigger picture - what are sibling branches exploring?
5. Balance depth (fewer, focused branches) with coverage (more, diverse branches)

You MUST use the make_branch_decision tool to provide your decision.
Never recommend an action without explaining your reasoning."""

    def _parse_decision_response(
        self,
        tool_call: dict,
        branch: Branch,
        context_warning: str | None,
    ) -> SplitRecommendation | None:
        """Parse the decision tool call response into a SplitRecommendation."""
        try:
            input_data = tool_call["input"]
            action_str = input_data.get("action", "continue")
            reasoning = input_data.get("reasoning", "No reasoning provided")

            # Map action string to enum
            action_map = {
                "continue": BranchAction.CONTINUE,
                "split": BranchAction.SPLIT,
                "wrap_up": BranchAction.WRAP_UP,
            }
            action = action_map.get(action_str, BranchAction.CONTINUE)

            if action == BranchAction.CONTINUE:
                logger.info(
                    f"Managing agent recommends CONTINUE for branch {branch.id}: "
                    f"{reasoning[:100]}..."
                )
                return SplitRecommendation.continue_exploring(
                    reasoning=reasoning,
                    context_warning=context_warning,
                )

            elif action == BranchAction.WRAP_UP:
                logger.info(
                    f"Managing agent recommends WRAP_UP for branch {branch.id}: "
                    f"{reasoning[:100]}..."
                )
                return SplitRecommendation.wrap_up(reasoning=reasoning)

            elif action == BranchAction.SPLIT:
                split_config = input_data.get("split_config", {})

                if not split_config or not split_config.get("branches"):
                    logger.warning("Split recommended but no branch configuration provided")
                    return SplitRecommendation.continue_exploring(
                        reasoning=f"Split was recommended but configuration was incomplete: {reasoning}",
                        context_warning=context_warning,
                    )

                branches_config = split_config.get("branches", [])
                criteria_str = split_config.get("criteria", "by_topic")

                # Map criteria string to enum
                criteria_map = {
                    "by_topic": SplitCriteria.BY_TOPIC,
                    "by_methodology": SplitCriteria.BY_METHODOLOGY,
                    "by_time_period": SplitCriteria.BY_TIME_PERIOD,
                    "by_application": SplitCriteria.BY_APPLICATION,
                    "by_theoretical_framework": SplitCriteria.BY_THEORETICAL_FRAMEWORK,
                    "by_data_type": SplitCriteria.BY_DATA_TYPE,
                    "custom": SplitCriteria.CUSTOM,
                }
                criteria = criteria_map.get(criteria_str, SplitCriteria.BY_TOPIC)

                paper_groups = [b.get("paper_ids", []) for b in branches_config]
                group_queries = [b.get("query", branch.query) for b in branches_config]
                group_labels = [b.get("label", f"Branch {i+1}") for i, b in enumerate(branches_config)]

                recommendation = SplitRecommendation(
                    should_split=True,
                    action=BranchAction.SPLIT,
                    num_branches=len(branches_config),
                    paper_groups=paper_groups,
                    group_queries=group_queries,
                    group_labels=group_labels,
                    split_criteria=criteria,
                    reasoning=reasoning,
                    context_warning=context_warning,
                )

                logger.info(
                    f"Managing agent recommends SPLIT for branch {branch.id} into "
                    f"{recommendation.num_branches} branches using {criteria.value}: {group_labels}"
                )
                logger.debug(f"Split reasoning: {recommendation.reasoning}")

                return recommendation

            else:
                logger.warning(f"Unknown action: {action_str}")
                return None

        except Exception as e:
            logger.error(f"Error parsing managing agent response: {e}")
            return None

    def _cluster_papers_by_criterion(
        self,
        branch: Branch,
        criterion: str,
    ) -> dict[str, list[str]]:
        """
        Cluster papers by the specified criterion.

        This is a helper that could be called if the agent uses the cluster_papers tool.
        For now, it provides basic clustering logic.
        """
        papers = branch.accumulated_papers
        clusters: dict[str, list[str]] = {}

        if criterion == "topic":
            # Cluster by primary field of study
            for paper_id, paper in papers.items():
                field = (paper.fields_of_study or ["Other"])[0]
                if field not in clusters:
                    clusters[field] = []
                clusters[field].append(paper_id)

        elif criterion == "time_period":
            # Cluster by decade
            for paper_id, paper in papers.items():
                if paper.year:
                    decade = f"{(paper.year // 10) * 10}s"
                else:
                    decade = "Unknown"
                if decade not in clusters:
                    clusters[decade] = []
                clusters[decade].append(paper_id)

        elif criterion == "methodology":
            # This would ideally use NLP to identify methodology
            # For now, use a simple heuristic based on title/abstract keywords
            clusters = {"Empirical": [], "Theoretical": [], "Survey": [], "Other": []}
            for paper_id, paper in papers.items():
                title_lower = paper.title.lower()
                if any(w in title_lower for w in ["survey", "review", "systematic"]):
                    clusters["Survey"].append(paper_id)
                elif any(w in title_lower for w in ["theory", "framework", "model"]):
                    clusters["Theoretical"].append(paper_id)
                elif any(w in title_lower for w in ["experiment", "study", "analysis", "evaluation"]):
                    clusters["Empirical"].append(paper_id)
                else:
                    clusters["Other"].append(paper_id)

        elif criterion == "application":
            # Cluster by application domain (from fields or keywords)
            for paper_id, paper in papers.items():
                # Use secondary fields as application domain hints
                fields = paper.fields_of_study or ["General"]
                app_field = fields[1] if len(fields) > 1 else fields[0]
                if app_field not in clusters:
                    clusters[app_field] = []
                clusters[app_field].append(paper_id)

        else:
            # Default: single cluster
            clusters["All"] = list(papers.keys())

        # Remove empty clusters
        return {k: v for k, v in clusters.items() if v}


async def create_managing_agent(
    config: ManagingAgentConfig | None = None,
) -> ManagingAgent:
    """
    Factory function to create a ManagingAgent with proper adapter.

    Args:
        config: Managing agent configuration

    Returns:
        Configured ManagingAgent instance

    Raises:
        ValueError: If OpenRouter configuration is not configured
    """
    from ..llm.adapters import OpenRouterAdapter
    from ..settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

    if config is None:
        from ..config.loader import ManagingAgentConfig
        config = ManagingAgentConfig()

    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is required for the managing agent. "
            "Please set it in your environment or .env file."
        )
    if not OPENROUTER_BASE_URL:
        raise ValueError(
            "OPENROUTER_BASE_URL environment variable is required for the managing agent. "
            "Please set it in your environment or .env file."
        )

    adapter = OpenRouterAdapter(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        model=config.model,
    )

    return ManagingAgent(llm_adapter=adapter, config=config)
