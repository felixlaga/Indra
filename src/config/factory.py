"""Factory functions to create backends from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.protocols import LLMProvider
    from ..halugate.protocols import HallucinationDetectorProtocol
    from ..orchestration.overseer import Overseer
    from .loader import ProfileConfig, SummarizerConfig, HaluGateConfig, OverseerConfig, PaperSourcesConfig


class MockLLMProvider:
    """Mock LLM provider for testing."""

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Return a mock completion."""
        return f"[Mock summary of: {prompt[:50]}...]"

    async def complete_messages(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Return a mock completion for messages."""
        return "[Mock response]"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockHaluGate:
    """Mock HaluGate for testing - always returns no hallucinations."""

    def __init__(self):
        from ..halugate.models import HallucinationResult

        self._result_class = HallucinationResult

    async def validate(
        self,
        context: str,
        question: str,
        answer: str,
    ):
        """Return a mock validation result with no hallucinations."""
        return self._result_class(
            fact_check_needed=True,
            hallucination_detected=False,
            spans=[],
            max_severity=0,
            nli_contradictions=0,
            raw_response="[Mock: no hallucinations]",
        )

    def compute_groundedness(self, result, answer: str) -> float:
        """Return perfect groundedness for mock."""
        return 1.0


class NullCitationProvider:
    """Citation provider that returns no related papers."""

    async def get_citations(self, paper_id: str, limit: int = 100) -> list:
        return []

    async def get_references(self, paper_id: str, limit: int = 100) -> list:
        return []

    async def get_citations_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 100,
    ) -> list:
        return []

    async def get_references_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 100,
    ) -> list:
        return []


def create_summarizer(config: SummarizerConfig) -> LLMProvider:
    """Create a summarizer backend from configuration.

    Args:
        config: Summarizer configuration

    Returns:
        LLMProvider instance (OpenRouterAdapter or Mock)

    Raises:
        ValueError: If backend type is not supported
    """
    if config.backend == "openrouter":
        from ..llm import OpenRouterAdapter

        if not config.api_key:
            raise ValueError("OpenRouter backend requires api_key")
        if not config.base_url:
            raise ValueError("OpenRouter backend requires base_url")

        return OpenRouterAdapter(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
        )

    elif config.backend == "mock":
        return MockLLMProvider()

    else:
        raise ValueError(f"Unsupported summarizer backend: {config.backend}")


def create_halugate(config: HaluGateConfig) -> HallucinationDetectorProtocol:
    """Create HaluGate from configuration.

    Args:
        config: HaluGate configuration

    Returns:
        HallucinationDetectorProtocol instance (local, HTTP, or mock)

    Raises:
        ValueError: If backend type is not supported or required fields are missing
    """
    if config.backend == "local":
        from ..halugate import LocalHaluGate

        return LocalHaluGate(
            device=config.device,
            use_sentinel=config.use_sentinel,
        )

    elif config.backend == "http":
        from ..halugate import HTTPHaluGate

        if not config.url:
            raise ValueError("HTTP HaluGate backend requires 'url' in config")

        return HTTPHaluGate(base_url=config.url)

    elif config.backend == "mock":
        return MockHaluGate()

    else:
        raise ValueError(f"Unsupported HaluGate backend: {config.backend}")


def create_overseer(
    halugate,
    summarizer,
    config: OverseerConfig,
) -> Overseer:
    """Create Overseer from configuration.

    Args:
        halugate: HaluGate instance for validation
        summarizer: LLM provider for summarization
        config: Overseer configuration

    Returns:
        Overseer instance with configured retry logic
    """
    from ..orchestration.overseer import Overseer

    return Overseer(
        halugate=halugate,
        summarizer=summarizer,
        max_retries=config.max_retries,
        groundedness_threshold=config.groundedness_threshold,
    )


def create_from_profile(
    profile: ProfileConfig,
) -> tuple:
    """Create all backends from a profile configuration.

    This is the main factory function that creates a complete set of backends
    from a configuration profile.

    Args:
        profile: Profile configuration containing all backend configs

    Returns:
        Tuple of (summarizer, halugate, overseer)

    Raises:
        ValueError: If any backend configuration is invalid
    """
    summarizer = create_summarizer(profile.summarizer)
    halugate = create_halugate(profile.halugate)
    overseer = create_overseer(halugate, summarizer, profile.overseer)

    return summarizer, halugate, overseer


def create_inner_loop(
    search_provider,
    summarizer,
    halugate,
    config,
    hypothesis_generator=None,
):
    """Create an InnerLoop from configuration.

    Args:
        search_provider: Semantic Scholar adapter
        summarizer: LLM provider for summarization
        halugate: HaluGate instance for validation
        config: InnerLoopConfig
        hypothesis_generator: Optional hypothesis generator

    Returns:
        InnerLoop instance
    """
    from ..orchestration.inner_loop import InnerLoop

    return InnerLoop(
        search_provider=search_provider,
        summarizer=summarizer,
        halugate=halugate,
        config=config,
        hypothesis_generator=hypothesis_generator,
    )


def create_iteration_loop(
    inner_loop,
    search_provider,
    context_estimator,
    config,
):
    """Create an IterationLoop from configuration.

    Args:
        inner_loop: InnerLoop instance
        search_provider: Semantic Scholar adapter
        context_estimator: Context estimator
        config: IterationLoopConfig

    Returns:
        IterationLoop instance
    """
    from ..orchestration.iteration_loop import IterationLoop

    return IterationLoop(
        inner_loop=inner_loop,
        search_provider=search_provider,
        context_estimator=context_estimator,
        config=config,
    )


def create_master_agent(
    search_provider,
    summarizer,
    halugate,
    config,
):
    """Create a MasterAgent from configuration.

    Args:
        search_provider: Semantic Scholar adapter
        summarizer: LLM provider for summarization
        halugate: HaluGate instance for validation
        config: ResearchLoopConfig

    Returns:
        MasterAgent instance
    """
    from ..orchestration.master_agent import MasterAgent

    return MasterAgent(
        search_provider=search_provider,
        summarizer=summarizer,
        halugate=halugate,
        config=config,
    )


def create_hypothesis_generator(
    llm_provider,
    hypotheses_per_batch: int = 3,
    temperature: float = 0.7,
):
    """Create a HypothesisGenerator.

    Args:
        llm_provider: LLM provider for generation
        hypotheses_per_batch: Number of hypotheses per batch
        temperature: LLM temperature

    Returns:
        HypothesisGenerator instance
    """
    from ..hypothesis.generator import HypothesisGenerator

    return HypothesisGenerator(
        llm_provider=llm_provider,
        hypotheses_per_batch=hypotheses_per_batch,
        temperature=temperature,
    )


def create_hypothesis_validator(
    halugate,
    groundedness_threshold: float = 0.8,
):
    """Create a HypothesisValidator.

    Args:
        halugate: HaluGate instance for validation
        groundedness_threshold: Minimum groundedness

    Returns:
        HypothesisValidator instance
    """
    from ..hypothesis.validator import HypothesisValidator

    return HypothesisValidator(
        halugate=halugate,
        groundedness_threshold=groundedness_threshold,
    )


def create_context_estimator(
    use_tiktoken: bool = False,
    chars_per_token: float = 4.0,
):
    """Create a ContextEstimator.

    Args:
        use_tiktoken: Whether to use tiktoken for accurate counting
        chars_per_token: Average characters per token

    Returns:
        ContextEstimator instance
    """
    from ..context.estimator import ContextEstimator

    return ContextEstimator(
        use_tiktoken=use_tiktoken,
        chars_per_token=chars_per_token,
    )


def create_branch_splitter(
    default_num_splits: int = 2,
):
    """Create a BranchSplitter.

    Args:
        default_num_splits: Default number of splits

    Returns:
        BranchSplitter instance
    """
    from ..context.splitter import BranchSplitter

    return BranchSplitter(default_num_splits=default_num_splits)


def create_reflection_agent(
    llm_provider,
    search_provider=None,
    config=None,
):
    """Create a ReflectionAgent for post-summarization evaluation.

    Args:
        llm_provider: LLM provider for reflection reasoning
        search_provider: Optional Semantic Scholar adapter for gap filling
        config: ReflectionConfig

    Returns:
        ReflectionAgent instance
    """
    from ..orchestration.reflection import ReflectionAgent

    return ReflectionAgent(
        llm_provider=llm_provider,
        search_provider=search_provider,
        config=config,
    )


def create_paper_provider(
    config: "PaperSourcesConfig",
    semantic_scholar_api_key: str | None = None,
) -> tuple:
    """
    Create paper search and citation providers from configuration.

    Args:
        config: Paper sources configuration
        semantic_scholar_api_key: Optional SS API key

    Returns:
        Tuple of (search_provider, citation_provider)
    """
    from ..semantic_scholar.adapters import SemanticScholarAdapter
    from ..arxiv.adapters import ArXivAdapter
    from ..paper_sources.composite import CompositeSearchProvider

    providers: list = []
    ss_adapter: SemanticScholarAdapter | None = None

    # Create requested providers
    if "semantic_scholar" in config.providers:
        ss_adapter = SemanticScholarAdapter(api_key=semantic_scholar_api_key)
        providers.append(ss_adapter)

    if "arxiv" in config.providers:
        arxiv_adapter = ArXivAdapter(
            categories=config.arxiv_categories,
            rate_limit_seconds=config.arxiv_rate_limit,
        )
        providers.append(arxiv_adapter)

    # Determine citation provider
    citation_provider: SemanticScholarAdapter | NullCitationProvider
    if ss_adapter:
        # Semantic Scholar has native citations
        citation_provider = ss_adapter
    else:
        # arXiv-only means no Semantic Scholar calls, including citation expansion.
        citation_provider = NullCitationProvider()

    # Single provider case
    if len(providers) == 1 and config.strategy == "single":
        if config.providers == ["arxiv"]:
            search_provider = CompositeSearchProvider(
                providers=providers,
                citation_provider=citation_provider,
                strategy=config.strategy,
                deduplicate=config.deduplication,
                prefer_provider=config.prefer_provider,
            )
        else:
            search_provider = providers[0]
    else:
        # Composite provider
        search_provider = CompositeSearchProvider(
            providers=providers,
            citation_provider=citation_provider,
            strategy=config.strategy,
            deduplicate=config.deduplication,
            prefer_provider=config.prefer_provider,
        )

    return search_provider, citation_provider
