"""Configuration system for model backends and research loop."""

from .loader import (
    load_config,
    load_config_from_yaml,
    ProfileConfig,
    SummarizerConfig,
    HaluGateConfig,
    OverseerConfig,
    InnerLoopConfig,
    IterationLoopConfig,
    BranchConfig,
    MasterAgentConfig,
    ResearchLoopConfig,
    # Phase 5: Reflection Loop config
    ReflectionConfig,
    # Soft guardrails configs
    PaperSelectionConfig,
    BranchSplittingConfig,
    SearchConfig,
)
from .factory import (
    create_summarizer,
    create_halugate,
    create_overseer,
    create_from_profile,
    create_inner_loop,
    create_iteration_loop,
    create_master_agent,
    create_hypothesis_generator,
    create_hypothesis_validator,
    create_context_estimator,
    create_branch_splitter,
    create_reflection_agent,
)

__all__ = [
    # Loader
    "load_config",
    "load_config_from_yaml",
    "ProfileConfig",
    "SummarizerConfig",
    "HaluGateConfig",
    "OverseerConfig",
    # Research Loop Config
    "InnerLoopConfig",
    "IterationLoopConfig",
    "BranchConfig",
    "MasterAgentConfig",
    "ResearchLoopConfig",
    # Phase 5: Reflection Loop Config
    "ReflectionConfig",
    # Soft guardrails configs
    "PaperSelectionConfig",
    "BranchSplittingConfig",
    "SearchConfig",
    # Factory - Core
    "create_summarizer",
    "create_halugate",
    "create_overseer",
    "create_from_profile",
    # Factory - Research Loop
    "create_inner_loop",
    "create_iteration_loop",
    "create_master_agent",
    "create_hypothesis_generator",
    "create_hypothesis_validator",
    "create_context_estimator",
    "create_branch_splitter",
    "create_reflection_agent",
]
