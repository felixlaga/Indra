"""Tool definitions for the Master Agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from .master_agent import MasterAgent


class ToolType(Enum):
    """Types of tools available to the Master Agent."""

    RUN_ITERATION = "run_iteration"
    SPLIT_BRANCH = "split_branch"
    SWITCH_MODE = "switch_mode"
    LAUNCH_RESEARCH_LOOP = "launch_research_loop"
    PRUNE_BRANCH = "prune_branch"
    GET_STATUS = "get_status"


@dataclass
class ToolDefinition:
    """Definition of a tool for the Master Agent."""

    name: str
    description: str
    parameters: dict[str, dict]
    required_params: list[str]


# Tool definitions for LLM-based agent decision making
TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    ToolType.RUN_ITERATION.value: ToolDefinition(
        name="run_iteration",
        description=(
            "Run one iteration on a branch. Searches for papers, summarizes them, "
            "validates summaries with HaluGate, and optionally generates hypotheses. "
            "Use this to advance research on a specific branch."
        ),
        parameters={
            "branch_id": {
                "type": "string",
                "description": "ID of the branch to run iteration on",
            },
            "mode": {
                "type": "string",
                "enum": ["search_summarize", "hypothesis"],
                "description": "Optional mode override for this iteration",
            },
        },
        required_params=["branch_id"],
    ),
    ToolType.SPLIT_BRANCH.value: ToolDefinition(
        name="split_branch",
        description=(
            "Split a branch into multiple child branches when context window is "
            "nearly full (>80%). This allows parallel exploration of different "
            "research directions. Use criteria to specify how to split."
        ),
        parameters={
            "branch_id": {
                "type": "string",
                "description": "ID of the branch to split",
            },
            "criteria": {
                "type": "string",
                "enum": ["by_topic", "by_time", "by_field", "by_citation_count", "random"],
                "description": "How to split the branch",
            },
        },
        required_params=["branch_id", "criteria"],
    ),
    ToolType.SWITCH_MODE.value: ToolDefinition(
        name="switch_mode",
        description=(
            "Switch the mode of a branch. Use 'hypothesis' mode when there are "
            "enough papers (≥10) to generate meaningful research hypotheses. "
            "Use 'search_summarize' mode for basic exploration."
        ),
        parameters={
            "branch_id": {
                "type": "string",
                "description": "ID of the branch to update",
            },
            "mode": {
                "type": "string",
                "enum": ["search_summarize", "hypothesis"],
                "description": "New mode for the branch",
            },
        },
        required_params=["branch_id", "mode"],
    ),
    ToolType.LAUNCH_RESEARCH_LOOP.value: ToolDefinition(
        name="launch_research_loop",
        description=(
            "Launch Big Loop 2 seeded with research hypotheses. Takes promising "
            "hypotheses from the current loop and starts a new loop that explores "
            "them as new research queries. Use this when you have high-quality "
            "hypotheses that warrant deeper investigation."
        ),
        parameters={
            "hypothesis_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of hypotheses to use as seeds for the new loop",
            },
        },
        required_params=["hypothesis_ids"],
    ),
    ToolType.PRUNE_BRANCH.value: ToolDefinition(
        name="prune_branch",
        description=(
            "Prune a branch to stop exploration. Use this when a branch has "
            "low-value results, is redundant with other branches, or has "
            "exhausted its search space."
        ),
        parameters={
            "branch_id": {
                "type": "string",
                "description": "ID of the branch to prune",
            },
            "reason": {
                "type": "string",
                "description": "Reason for pruning (for logging)",
            },
        },
        required_params=["branch_id"],
    ),
    ToolType.GET_STATUS.value: ToolDefinition(
        name="get_status",
        description=(
            "Get status of the loop or a specific branch. Returns information "
            "about papers found, summaries validated, context usage, and more."
        ),
        parameters={
            "branch_id": {
                "type": "string",
                "description": "Optional branch ID for branch-specific status",
            },
        },
        required_params=[],
    ),
}


def get_tool_schema() -> list[dict]:
    """
    Get OpenAI-style function schema for all tools.

    Returns:
        List of tool schemas for LLM function calling
    """
    schemas = []

    for tool_def in TOOL_DEFINITIONS.values():
        schema = {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": {
                    "type": "object",
                    "properties": tool_def.parameters,
                    "required": tool_def.required_params,
                },
            },
        }
        schemas.append(schema)

    return schemas


def get_tool_descriptions() -> str:
    """
    Get human-readable tool descriptions.

    Returns:
        Formatted string describing all available tools
    """
    lines = ["Available tools:\n"]

    for name, tool_def in TOOL_DEFINITIONS.items():
        lines.append(f"- {name}: {tool_def.description}")
        if tool_def.required_params:
            lines.append(f"  Required: {', '.join(tool_def.required_params)}")

    return "\n".join(lines)


@dataclass
class ToolCall:
    """A tool call from the LLM."""

    tool_name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    result: Any
    error: str | None = None


class ToolExecutor:
    """
    Executes tool calls for the Master Agent.

    Maps tool names to agent methods and handles execution.
    """

    def __init__(self, agent: MasterAgent):
        """
        Initialize the tool executor.

        Args:
            agent: Master agent instance to execute tools on
        """
        self.agent = agent

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call.

        Args:
            tool_call: Tool call to execute

        Returns:
            ToolResult with success status and result/error
        """
        try:
            if tool_call.tool_name == ToolType.RUN_ITERATION.value:
                result = await self.agent.run_iteration(
                    branch_id=tool_call.arguments["branch_id"],
                    mode=tool_call.arguments.get("mode"),
                )
                return ToolResult(success=True, result=result)

            elif tool_call.tool_name == ToolType.SPLIT_BRANCH.value:
                result = await self.agent.split_branch(
                    branch_id=tool_call.arguments["branch_id"],
                    criteria=tool_call.arguments["criteria"],
                )
                return ToolResult(success=True, result=result)

            elif tool_call.tool_name == ToolType.SWITCH_MODE.value:
                self.agent.switch_mode(
                    branch_id=tool_call.arguments["branch_id"],
                    mode=tool_call.arguments["mode"],
                )
                return ToolResult(success=True, result="Mode switched successfully")

            elif tool_call.tool_name == ToolType.LAUNCH_RESEARCH_LOOP.value:
                result = await self.agent.launch_research_loop(
                    hypothesis_ids=tool_call.arguments["hypothesis_ids"],
                )
                return ToolResult(success=True, result=result)

            elif tool_call.tool_name == ToolType.PRUNE_BRANCH.value:
                self.agent.prune_branch(
                    branch_id=tool_call.arguments["branch_id"],
                    reason=tool_call.arguments.get("reason", ""),
                )
                return ToolResult(success=True, result="Branch pruned successfully")

            elif tool_call.tool_name == ToolType.GET_STATUS.value:
                result = self.agent.get_status(
                    branch_id=tool_call.arguments.get("branch_id"),
                )
                return ToolResult(success=True, result=result)

            else:
                return ToolResult(
                    success=False,
                    result=None,
                    error=f"Unknown tool: {tool_call.tool_name}",
                )

        except Exception as e:
            return ToolResult(
                success=False,
                result=None,
                error=str(e),
            )

    async def execute_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """
        Execute multiple tool calls.

        Args:
            tool_calls: List of tool calls to execute

        Returns:
            List of tool results
        """
        results = []
        for call in tool_calls:
            result = await self.execute(call)
            results.append(result)
        return results
