"""Orchestration module for the recursive research agent system.

This module provides the 4-layer recursive research agent:
- Layer 1: InnerLoop - Atomic search-summarize-validate unit
- Layer 2: IterationLoop - Depth expansion via citation traversal
- Layer 3: MasterAgent - Orchestrator with tool-based control
- Layer 4: Big Loop 2 - Hypothesis-seeded recursive exploration
- Phase 5: ReflectionAgent - Post-summarization evaluation and gap identification
"""

from .overseer import Overseer
from .models import (
    BranchStatus,
    InnerLoopMode,
    ValidatedSummary,
    ResearchHypothesis,
    IterationResult,
    Branch,
    LoopState,
    LoopStatus,
    BranchSplitResult,
)
from .inner_loop import InnerLoop
from .iteration_loop import IterationLoop
from .master_agent import MasterAgent, ResearchSession
from .managing_agent import (
    ManagingAgent,
    SplitRecommendation,
    create_managing_agent,
    BranchAction,
    SplitCriteria,
)
from .branch_manager import BranchManager
from .state_store import StateStore
from .reflection import ReflectionAgent, ReflectionResult, create_reflection_agent
from .tools import (
    ToolType,
    ToolDefinition,
    ToolCall,
    ToolResult,
    ToolExecutor,
    get_tool_schema,
    get_tool_descriptions,
    TOOL_DEFINITIONS,
)
from .query_planner import (
    QueryPlanner,
    SearchPlan,
    DiversityDimension,
    SaturationCriterion,
    create_search_plan,
)

__all__ = [
    # Original
    "Overseer",
    # Models
    "BranchStatus",
    "InnerLoopMode",
    "ValidatedSummary",
    "ResearchHypothesis",
    "IterationResult",
    "Branch",
    "LoopState",
    "LoopStatus",
    "BranchSplitResult",
    # Layer 1
    "InnerLoop",
    # Layer 2
    "IterationLoop",
    # Layer 3
    "MasterAgent",
    "ResearchSession",
    # Managing Agent
    "ManagingAgent",
    "SplitRecommendation",
    "create_managing_agent",
    "BranchAction",
    "SplitCriteria",
    # Phase 5: Reflection
    "ReflectionAgent",
    "ReflectionResult",
    "create_reflection_agent",
    # Branch Management
    "BranchManager",
    "StateStore",
    # Tools
    "ToolType",
    "ToolDefinition",
    "ToolCall",
    "ToolResult",
    "ToolExecutor",
    "get_tool_schema",
    "get_tool_descriptions",
    "TOOL_DEFINITIONS",
    # Query Planning
    "QueryPlanner",
    "SearchPlan",
    "DiversityDimension",
    "SaturationCriterion",
    "create_search_plan",
]
