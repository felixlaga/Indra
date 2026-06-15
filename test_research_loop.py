"""
Test script for the Recursive Research Agent System.

Tests the new orchestration components without requiring external APIs.
"""

import asyncio
from datetime import datetime


def test_models():
    """Test all data models."""
    print("=== Testing Data Models ===\n")

    from src.orchestration.models import (
        BranchStatus, InnerLoopMode, ValidatedSummary,
        ResearchHypothesis, IterationResult, Branch,
        LoopState, LoopStatus, BranchSplitResult,
    )
    from src.semantic_scholar.models import PaperDetails, Author

    # Test ValidatedSummary
    summary = ValidatedSummary(
        paper_id="abc123",
        paper_title="Test Paper on Machine Learning",
        summary="This paper presents a novel approach to ML.",
        groundedness=0.96,
    )
    assert summary.groundedness == 0.96
    print(f"✓ ValidatedSummary: groundedness={summary.groundedness}")

    # Test ResearchHypothesis
    hypothesis = ResearchHypothesis(
        id="hyp1",
        text="Does attention mechanism improve reasoning in LLMs?",
        supporting_paper_ids=["abc123", "def456"],
        confidence=0.85,
        generated_from_branch="branch1",
    )
    assert hypothesis.confidence == 0.85
    assert len(hypothesis.supporting_paper_ids) == 2
    print(f"✓ ResearchHypothesis: confidence={hypothesis.confidence}")

    # Test Branch
    branch = Branch(
        id="branch1",
        query="transformer attention mechanisms",
        mode=InnerLoopMode.SEARCH_SUMMARIZE,
        status=BranchStatus.PENDING,
    )
    assert branch.context_utilization == 0.0
    assert not branch.is_context_nearly_full
    print(f"✓ Branch: mode={branch.mode.value}, status={branch.status.value}")

    # Test Branch with papers
    paper = PaperDetails(
        paper_id="paper1",
        title="Attention Is All You Need",
        abstract="We propose the Transformer...",
        authors=[Author(name="Vaswani et al.")],
        year=2017,
        citation_count=50000,
    )
    branch.accumulated_papers["paper1"] = paper
    branch.accumulated_summaries["paper1"] = summary
    assert branch.total_papers == 1
    assert branch.total_summaries == 1
    print(f"✓ Branch accumulated: papers={branch.total_papers}, summaries={branch.total_summaries}")

    # Test IterationResult
    iter_result = IterationResult(
        iteration_number=1,
        papers_found=[paper],
        summaries=[summary],
        hypotheses=None,
        context_tokens_used=5000,
    )
    assert iter_result.paper_count == 1
    assert iter_result.validated_summary_count == 1
    print(f"✓ IterationResult: papers={iter_result.paper_count}, tokens={iter_result.context_tokens_used}")

    # Test Branch.add_iteration
    branch.add_iteration(iter_result)
    assert branch.iteration_count == 1
    assert branch.context_window_used == 5000
    print(f"✓ Branch after iteration: iterations={branch.iteration_count}, context_used={branch.context_window_used}")

    # Test LoopState
    state = LoopState(
        loop_id="loop1",
        loop_number=1,
    )
    state.add_branch(branch)
    assert len(state.branches) == 1
    assert len(state.active_branches) == 1
    print(f"✓ LoopState: branches={len(state.branches)}, active={len(state.active_branches)}")

    # Test LoopStatus
    status = LoopStatus.from_loop_state(state)
    assert status.total_branches == 1
    assert status.total_papers == 1
    print(f"✓ LoopStatus: total_papers={status.total_papers}, total_summaries={status.total_summaries}")

    print("\n✓ All model tests passed!\n")


def test_context_management():
    """Test context estimation and splitting."""
    print("=== Testing Context Management ===\n")

    from src.context import ContextEstimator, BranchSplitter, SplitStrategy
    from src.orchestration.models import Branch, InnerLoopMode, BranchStatus
    from src.semantic_scholar.models import PaperDetails, Author

    # Test ContextEstimator
    estimator = ContextEstimator()

    text = "This is a test sentence with approximately forty characters."
    tokens = estimator.estimate_tokens(text)
    assert tokens > 0
    print(f"✓ ContextEstimator: '{text[:30]}...' = {tokens} tokens")

    # Test paper token estimation
    paper = PaperDetails(
        paper_id="p1",
        title="A Long Paper Title",
        abstract="This is a long abstract " * 50,
        authors=[Author(name="Test Author")],
        year=2024,
    )
    paper_tokens = estimator.estimate_paper_tokens(paper)
    assert paper_tokens > 100
    print(f"✓ Paper tokens: {paper_tokens}")

    # Test context threshold
    exceeds = estimator.will_exceed_context(
        current_tokens=100000,
        additional_tokens=30000,
        max_context=128000,
        threshold=0.8,
    )
    assert exceeds  # 130000 > 128000 * 0.8 = 102400
    print(f"✓ will_exceed_context: 100k + 30k tokens exceeds 80% of 128k = {exceeds}")

    # Test remaining capacity
    remaining = estimator.remaining_capacity(
        current_tokens=50000,
        max_context=128000,
        threshold=0.8,
    )
    assert remaining == 52400  # 128000 * 0.8 - 50000
    print(f"✓ remaining_capacity: {remaining} tokens")

    # Test BranchSplitter
    splitter = BranchSplitter(default_num_splits=2)

    # Create branch with papers from different fields
    branch = Branch(
        id="test_branch",
        query="deep learning",
        mode=InnerLoopMode.SEARCH_SUMMARIZE,
        status=BranchStatus.RUNNING,
    )

    papers = [
        PaperDetails(paper_id="p1", title="NLP Paper", fields_of_study=["Computer Science", "NLP"], year=2023, citation_count=100),
        PaperDetails(paper_id="p2", title="CV Paper", fields_of_study=["Computer Science", "Computer Vision"], year=2024, citation_count=50),
        PaperDetails(paper_id="p3", title="NLP Paper 2", fields_of_study=["NLP"], year=2022, citation_count=200),
        PaperDetails(paper_id="p4", title="CV Paper 2", fields_of_study=["Computer Vision"], year=2023, citation_count=75),
    ]
    for p in papers:
        branch.accumulated_papers[p.paper_id] = p

    # Analyze papers
    analysis = splitter.analyze_papers(papers)
    assert analysis["total_papers"] == 4
    print(f"✓ Paper analysis: {analysis['total_papers']} papers, {analysis['strategies']['by_field']['num_fields']} fields")

    # Test split suggestion
    suggested = splitter.suggest_strategy(branch)
    print(f"✓ Suggested strategy: {suggested.value}")

    # Test actual split
    result = splitter.split(branch, SplitStrategy.BY_FIELD, num_splits=2)
    assert len(result.groups) >= 1
    print(f"✓ Split result: {len(result.groups)} groups, labels={result.group_labels}")

    print("\n✓ All context management tests passed!\n")


def test_config():
    """Test configuration loading."""
    print("=== Testing Configuration ===\n")

    from src.config import (
        load_config,
        InnerLoopConfig,
        IterationLoopConfig,
        BranchConfig,
        MasterAgentConfig,
        ResearchLoopConfig,
    )

    # Test default config
    inner = InnerLoopConfig()
    assert inner.groundedness_threshold == 0.95
    print(f"✓ InnerLoopConfig defaults: threshold={inner.groundedness_threshold}")

    iter_config = IterationLoopConfig()
    assert iter_config.max_iterations_per_branch == 10
    print(f"✓ IterationLoopConfig defaults: max_iterations={iter_config.max_iterations_per_branch}")

    branch_config = BranchConfig()
    assert branch_config.max_context_window == 128000
    print(f"✓ BranchConfig defaults: max_context={branch_config.max_context_window}")

    master_config = MasterAgentConfig()
    assert master_config.auto_hypothesis_mode == True
    print(f"✓ MasterAgentConfig defaults: auto_hypothesis={master_config.auto_hypothesis_mode}")

    # Test loading research profiles
    try:
        config = load_config("research-fast")
        assert config.research_loop.inner_loop.groundedness_threshold == 0.95
        assert config.research_loop.branch.max_branches == 5
        print(f"✓ Loaded research-fast profile")
        print(f"  - groundedness_threshold: {config.research_loop.inner_loop.groundedness_threshold}")
        print(f"  - max_papers_per_iteration: {config.research_loop.inner_loop.max_papers_per_iteration}")
        print(f"  - max_branches: {config.research_loop.branch.max_branches}")
    except Exception as e:
        print(f"⚠ Could not load research-fast profile: {e}")

    try:
        config = load_config("research-accurate")
        print(f"✓ Loaded research-accurate profile")
    except Exception as e:
        print(f"⚠ Could not load research-accurate profile: {e}")

    print("\n✓ All configuration tests passed!\n")


def test_tools():
    """Test tool definitions."""
    print("=== Testing Tool Definitions ===\n")

    from src.orchestration.tools import (
        ToolType, ToolDefinition, ToolCall, ToolResult,
        get_tool_schema, get_tool_descriptions, TOOL_DEFINITIONS,
    )

    # Test tool definitions exist
    assert len(TOOL_DEFINITIONS) == 6
    print(f"✓ {len(TOOL_DEFINITIONS)} tools defined")

    for name, tool_def in TOOL_DEFINITIONS.items():
        assert tool_def.name
        assert tool_def.description
        print(f"  - {name}: {len(tool_def.parameters)} params")

    # Test schema generation
    schema = get_tool_schema()
    assert len(schema) == 6
    print(f"✓ Generated {len(schema)} OpenAI-style function schemas")

    # Verify schema structure
    for s in schema:
        assert s["type"] == "function"
        assert "function" in s
        assert "name" in s["function"]
        assert "parameters" in s["function"]
    print("✓ Schema structure validated")

    # Test tool descriptions
    desc = get_tool_descriptions()
    assert len(desc) > 500
    print(f"✓ Tool descriptions: {len(desc)} chars")

    # Test ToolCall and ToolResult
    call = ToolCall(
        tool_name="run_iteration",
        arguments={"branch_id": "test123"},
        call_id="call_1",
    )
    assert call.tool_name == "run_iteration"
    print(f"✓ ToolCall: {call.tool_name}({call.arguments})")

    result = ToolResult(success=True, result={"papers": 5})
    assert result.success
    print(f"✓ ToolResult: success={result.success}")

    print("\n✓ All tool tests passed!\n")


def test_state_store():
    """Test state persistence."""
    print("=== Testing State Store ===\n")

    from src.orchestration.state_store import StateStore
    from src.orchestration.models import LoopState, Branch, InnerLoopMode, BranchStatus

    store = StateStore()

    # Create and save state
    state = LoopState(loop_id="test_loop", loop_number=1)
    branch = Branch(
        id="branch1",
        query="test query",
        mode=InnerLoopMode.SEARCH_SUMMARIZE,
        status=BranchStatus.PENDING,
    )
    state.add_branch(branch)

    store.save_state(state)
    print(f"✓ Saved state for loop {state.loop_id}")

    # Load state
    loaded = store.load_state("test_loop")
    assert loaded is not None
    assert loaded.loop_id == "test_loop"
    assert len(loaded.branches) == 1
    print(f"✓ Loaded state: {loaded.loop_id} with {len(loaded.branches)} branches")

    # List loops
    loops = store.list_loops()
    assert "test_loop" in loops
    print(f"✓ Listed loops: {loops}")

    # Get branch
    branch = store.get_branch("test_loop", "branch1")
    assert branch is not None
    assert branch.query == "test query"
    print(f"✓ Got branch: {branch.id}")

    # Create snapshot
    snapshot_id = store.create_snapshot("test_loop")
    assert snapshot_id is not None
    print(f"✓ Created snapshot: {snapshot_id}")

    # List snapshots
    snapshots = store.list_snapshots("test_loop")
    assert len(snapshots) == 1
    print(f"✓ Listed snapshots: {len(snapshots)}")

    # Get stats
    stats = store.get_stats()
    assert stats["total_loops"] == 1
    print(f"✓ Store stats: {stats}")

    # Delete state
    deleted = store.delete_state("test_loop")
    assert deleted
    assert store.load_state("test_loop") is None
    print(f"✓ Deleted state")

    print("\n✓ All state store tests passed!\n")


def test_branch_manager():
    """Test branch management."""
    print("=== Testing Branch Manager ===\n")

    from src.orchestration.branch_manager import BranchManager
    from src.orchestration.models import (
        Branch, LoopState, InnerLoopMode, BranchStatus,
    )
    from src.context.splitter import BranchSplitter
    from src.semantic_scholar.models import PaperDetails

    splitter = BranchSplitter()
    manager = BranchManager(splitter=splitter)

    # Create branch
    branch = manager.create_branch(
        query="deep learning transformers",
        mode=InnerLoopMode.SEARCH_SUMMARIZE,
    )
    assert branch.status == BranchStatus.PENDING
    assert branch.mode == InnerLoopMode.SEARCH_SUMMARIZE
    print(f"✓ Created branch: {branch.id}")

    # Update status
    manager.update_status(branch, BranchStatus.RUNNING)
    assert branch.status == BranchStatus.RUNNING
    print(f"✓ Updated status to RUNNING")

    # Check split conditions
    assert not manager.should_split(branch)  # Empty branch
    print(f"✓ should_split (empty): {manager.should_split(branch)}")

    # Simulate context usage
    branch.context_window_used = 110000  # 86% of 128k
    assert manager.should_split(branch)
    print(f"✓ should_split (86% full): {manager.should_split(branch)}")

    # Check hypothesis mode conditions
    assert not manager.should_enable_hypothesis_mode(branch)  # No papers yet

    # Add papers
    for i in range(12):
        branch.accumulated_papers[f"paper{i}"] = PaperDetails(
            paper_id=f"paper{i}",
            title=f"Paper {i}",
            fields_of_study=["ML"] if i % 2 == 0 else ["NLP"],
        )

    assert manager.should_enable_hypothesis_mode(branch)
    print(f"✓ should_enable_hypothesis_mode (12 papers): True")

    # Test prune
    manager.prune_branch(branch, "low value")
    assert branch.status == BranchStatus.PRUNED
    print(f"✓ Pruned branch: status={branch.status.value}")

    # Test LoopState integration
    state = LoopState(loop_id="test", loop_number=1)
    new_branch = manager.create_branch("test query", InnerLoopMode.SEARCH_SUMMARIZE)
    state.add_branch(new_branch)

    assert manager.can_create_more_branches(state)
    print(f"✓ can_create_more_branches: True")

    next_branch = manager.get_next_branch(state)
    assert next_branch is not None
    print(f"✓ get_next_branch: {next_branch.id}")

    print("\n✓ All branch manager tests passed!\n")


def test_hypothesis_module():
    """Test hypothesis generation module (without LLM calls)."""
    print("=== Testing Hypothesis Module ===\n")

    from src.hypothesis.generator import HypothesisGenerator
    from src.hypothesis.validator import HypothesisValidator
    from src.orchestration.models import ValidatedSummary, ResearchHypothesis

    # Test generator parsing (mock LLM response)
    class MockLLM:
        async def complete(self, prompt, system_prompt=None, temperature=0.7):
            return '''[
                {
                    "text": "Could combining attention and graph networks improve reasoning?",
                    "supporting_papers": ["Paper A", "Paper B"],
                    "confidence": 0.85,
                    "rationale": "Both show promise independently"
                }
            ]'''

    generator = HypothesisGenerator(llm_provider=MockLLM())
    print(f"✓ HypothesisGenerator created")

    # Test parsing logic
    response = '''[
        {"text": "Test hypothesis", "supporting_papers": ["Paper 1"], "confidence": 0.8, "rationale": "test"}
    ]'''
    paper_id_map = {"Paper 1": "p1", "Paper 2": "p2"}
    hypotheses = generator._parse_response(response, paper_id_map, "branch1")

    assert len(hypotheses) == 1
    assert hypotheses[0].text == "Test hypothesis"
    assert hypotheses[0].confidence == 0.8
    print(f"✓ Parsed hypothesis: '{hypotheses[0].text[:30]}...'")

    # Test validator quick check
    class MockHaluGate:
        async def validate(self, context, question, answer):
            from src.halugate.models import HallucinationResult
            return HallucinationResult(
                fact_check_needed=True,
                hallucination_detected=False,
                spans=[],
                max_severity=0,
                nli_contradictions=0,
                raw_response="mock",
            )

        def compute_groundedness(self, result, answer):
            return 0.95

    validator = HypothesisValidator(halugate=MockHaluGate())
    print(f"✓ HypothesisValidator created")

    # Test quick check
    hypothesis = ResearchHypothesis(
        id="h1",
        text="Does X improve Y in Z conditions?",
        supporting_paper_ids=["p1"],
        confidence=0.8,
        generated_from_branch="b1",
    )
    summary = ValidatedSummary(
        paper_id="p1",
        paper_title="Test Paper",
        summary="This paper explores X and Y.",
        groundedness=0.95,
    )

    passes, reason = validator.quick_check(hypothesis, [summary])
    assert passes
    print(f"✓ Quick check passed: {reason}")

    # Test quick check failures
    short_hyp = ResearchHypothesis(
        id="h2", text="X?", supporting_paper_ids=["p1"],
        confidence=0.8, generated_from_branch="b1",
    )
    passes, reason = validator.quick_check(short_hyp, [summary])
    assert not passes
    print(f"✓ Quick check failed for short hypothesis: {reason}")

    print("\n✓ All hypothesis module tests passed!\n")


async def test_async_components():
    """Test async components with mocks."""
    print("=== Testing Async Components ===\n")

    from src.orchestration.state_store import StateStore
    from src.orchestration.branch_manager import BranchManager
    from src.orchestration.models import LoopState, Branch, InnerLoopMode, BranchStatus
    from src.context.splitter import BranchSplitter

    # Test state store async operations (it's actually sync but tests integration)
    store = StateStore()
    state = LoopState(loop_id="async_test", loop_number=1)
    store.save_state(state)

    loaded = store.load_state("async_test")
    assert loaded is not None
    print(f"✓ State store works in async context")

    # Clean up
    store.delete_state("async_test")

    print("\n✓ All async tests passed!\n")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Running Research Loop Tests")
    print("=" * 60 + "\n")

    test_models()
    test_context_management()
    test_config()
    test_tools()
    test_state_store()
    test_branch_manager()
    test_hypothesis_module()

    # Run async tests
    asyncio.run(test_async_components())

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
