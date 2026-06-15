"""Configuration loader with Pydantic validation and env var expansion."""

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class SummarizerConfig(BaseModel):
    """Configuration for summarizer backend."""

    backend: Literal["openrouter", "mock"] = "openrouter"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class HaluGateConfig(BaseModel):
    """Configuration for HaluGate backend (main branch's 3-stage pipeline)."""

    backend: Literal["local", "http", "mock"] = "local"
    use_sentinel: bool = True
    device: str = "cpu"
    url: str | None = None  # For HTTP backend


class OverseerConfig(BaseModel):
    """Configuration for Overseer retry logic."""

    max_retries: int = 2
    groundedness_threshold: float = 0.8


class InnerLoopConfig(BaseModel):
    """Configuration for the Inner Loop (Layer 1)."""

    groundedness_threshold: float = 0.95  # Higher threshold for research loop
    max_papers_per_iteration: int = 20
    parallel_summarization: bool = True
    max_summarization_concurrency: int = 5
    fetch_full_text: bool = True  # Whether to fetch full PDF text (slower but more detailed)


class IterationLoopConfig(BaseModel):
    """Configuration for the Iteration Loop (Layer 2)."""

    max_iterations_per_branch: int = 10
    citation_depth: int = 2  # How many levels of citations to follow
    max_citations_per_paper: int = 5  # Reduced from 20 to limit explosion
    max_references_per_paper: int = 5  # Reduced from 20 to limit explosion
    include_references: bool = True  # Also follow references, not just citations


class BranchConfig(BaseModel):
    """Configuration for branch management."""

    max_context_window: int = 128000
    context_split_threshold: float = 0.8  # Split when context is 80% full
    min_papers_for_hypothesis_mode: int = 10
    max_branches: int = 10


class ManagingAgentConfig(BaseModel):
    """Configuration for the Managing Agent."""

    enabled: bool = False
    model: str = "anthropic/claude-3-5-sonnet"
    min_papers_before_evaluation: int = 5
    evaluation_interval: int = 2  # Evaluate every N iterations


class ExecutionAgentConfig(BaseModel):
    """Configuration for Execution Agents."""

    model: str = "anthropic/claude-3-haiku"


class ReflectionConfig(BaseModel):
    """Configuration for the Reflection Loop (Phase 5).

    Soft guardrails - these are suggestions, the agent can override with justification.
    """

    enabled: bool = True
    min_papers_for_reflection: int = 5  # Minimum papers before triggering reflection
    auto_search_gaps: bool = True  # Automatically search for papers to fill gaps
    max_gap_searches: int = 3  # Maximum gap-filling searches per reflection
    coverage_threshold: float = 0.8  # Coverage score below which gaps are flagged
    reflection_interval: int = 1  # Reflect after every N iterations (0=only at end)


class PaperSelectionConfig(BaseModel):
    """Soft guardrails for paper selection.

    These are suggestions - the agent can go outside these ranges if justified.
    """

    suggested_range: tuple[int, int] = (5, 30)  # [min, max] papers suggested
    diversity_reminder: bool = True  # Prompt includes diversity consideration


class BranchSplittingConfig(BaseModel):
    """Soft guardrails for branch splitting.

    These are suggestions - the agent can override with justification.
    """

    context_warning: float = 0.7  # Agent gets notified at this threshold, not forced
    max_branches_suggestion: int = 5  # Soft limit, agent can request more


class SearchConfig(BaseModel):
    """Soft guardrails for search behavior.

    These are suggestions to help the agent make good decisions.
    """

    initial_pool_size: int = 50  # Fetch many papers, agent filters down
    min_papers_before_split: int = 5  # Suggestion before considering split


class PaperSourcesConfig(BaseModel):
    """Configuration for paper search providers."""

    providers: list[Literal["semantic_scholar", "arxiv"]] = ["semantic_scholar"]
    strategy: Literal["parallel", "fallback", "single"] = "single"
    deduplication: bool = True
    prefer_provider: Literal["semantic_scholar", "arxiv"] = "semantic_scholar"
    arxiv_categories: list[str] | None = None  # e.g., ["cs.LG", "cs.AI"]
    arxiv_rate_limit: float = 3.0  # Seconds between arXiv requests


class MasterAgentConfig(BaseModel):
    """Configuration for the Master Agent (Layer 3)."""

    max_parallel_branches: int = 5
    auto_prune_enabled: bool = True
    auto_split_enabled: bool = True
    auto_hypothesis_mode: bool = True  # Auto-switch to hypothesis mode when enough papers
    managing_agent: ManagingAgentConfig = ManagingAgentConfig()
    execution_agent: ExecutionAgentConfig = ExecutionAgentConfig()


class ResearchLoopConfig(BaseModel):
    """Configuration for the entire research loop system."""

    inner_loop: InnerLoopConfig = InnerLoopConfig()
    iteration_loop: IterationLoopConfig = IterationLoopConfig()
    branch: BranchConfig = BranchConfig()
    master_agent: MasterAgentConfig = MasterAgentConfig()
    reflection: ReflectionConfig = ReflectionConfig()
    # Soft guardrails (suggestions, not hard limits)
    paper_selection: PaperSelectionConfig = PaperSelectionConfig()
    branch_splitting: BranchSplittingConfig = BranchSplittingConfig()
    search: SearchConfig = SearchConfig()


class ProfileConfig(BaseModel):
    """Configuration profile containing all backend configs."""

    summarizer: SummarizerConfig
    halugate: HaluGateConfig
    overseer: OverseerConfig = OverseerConfig()
    research_loop: ResearchLoopConfig = ResearchLoopConfig()
    paper_sources: PaperSourcesConfig = PaperSourcesConfig()


class ConfigFile(BaseModel):
    """Root configuration file structure."""

    profiles: dict[str, ProfileConfig]


def expand_env_vars(value: str) -> str:
    """Expand ${VAR} or $VAR references in string with environment variables.

    Args:
        value: String potentially containing env var references

    Returns:
        String with env vars expanded
    """
    if not isinstance(value, str):
        return value

    # Replace ${VAR} style references
    pattern = r"\$\{([^}]+)\}"

    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return re.sub(pattern, replacer, value)


def expand_env_vars_recursive(data):
    """Recursively expand env vars in nested dict/list structures.

    Args:
        data: Dict, list, or primitive value

    Returns:
        Data structure with all env vars expanded
    """
    if isinstance(data, dict):
        return {k: expand_env_vars_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [expand_env_vars_recursive(item) for item in data]
    elif isinstance(data, str):
        return expand_env_vars(data)
    else:
        return data


def load_config_from_yaml(config_path: Path, profile_name: str) -> ProfileConfig:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config YAML file
        profile_name: Name of profile to load

    Returns:
        ProfileConfig for the requested profile

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValidationError: If config is invalid
        KeyError: If profile doesn't exist
    """
    with open(config_path) as f:
        raw_data = yaml.safe_load(f)

    # Expand environment variables
    expanded_data = expand_env_vars_recursive(raw_data)

    # Validate structure
    config_file = ConfigFile(**expanded_data)

    # Get requested profile
    if profile_name not in config_file.profiles:
        available = ", ".join(config_file.profiles.keys())
        raise KeyError(
            f"Profile '{profile_name}' not found. " f"Available profiles: {available}"
        )

    return config_file.profiles[profile_name]


def load_config_from_env() -> ProfileConfig:
    """Load configuration from environment variables (fallback mode).

    This provides backward compatibility when config file doesn't exist.
    Uses the same env vars as before.

    Returns:
        ProfileConfig constructed from environment variables
    """
    # Summarizer config
    summarizer = SummarizerConfig(
        backend="openrouter",
        model=os.environ.get("OPENROUTER_MODEL") or "upstage/solar-pro-3:free",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url=os.environ.get("OPENROUTER_BASE_URL"),
    )

    # HaluGate config - default to local for main branch
    halugate = HaluGateConfig(
        backend="local",
        use_sentinel=True,
        device="cpu",
    )

    # Overseer config - use defaults
    overseer = OverseerConfig()

    # Research loop config - use defaults
    research_loop = ResearchLoopConfig()

    return ProfileConfig(
        summarizer=summarizer,
        halugate=halugate,
        overseer=overseer,
        research_loop=research_loop,
    )


def load_config(
    profile: str | None = None,
    config_path: Path | None = None,
) -> ProfileConfig:
    """Load configuration from YAML file or environment variables.

    This is the main entry point for loading configuration. It tries to load
    from a YAML config file first, and falls back to environment variables
    if the file doesn't exist (for backward compatibility).

    Args:
        profile: Profile name to load. If None, uses MODEL_PROFILE env var
                or "dev-fast" as default.
        config_path: Path to config file. If None, uses src/config/models.yaml
                    in the project root.

    Returns:
        ProfileConfig with all backend configurations

    Raises:
        ValidationError: If configuration is invalid
        KeyError: If requested profile doesn't exist
    """
    # Determine profile name
    if profile is None:
        profile = os.environ.get("MODEL_PROFILE") or "dev-fast"

    # Determine config file path
    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "src" / "config" / "models.yaml"

    # Try to load from YAML, fall back to env vars
    if config_path.exists():
        try:
            return load_config_from_yaml(config_path, profile)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            print("Falling back to environment variables...")
            return load_config_from_env()
    else:
        print(f"Config file {config_path} not found, using environment variables")
        return load_config_from_env()
