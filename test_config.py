"""
Configuration System Tests

Tests for the YAML configuration loader and factory functions.
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def test_load_config_from_yaml():
    """Test loading configuration from YAML file."""
    print("=" * 60)
    print("TEST 1: Load configuration from YAML")
    print("=" * 60)

    from src.config.loader import load_config_from_yaml

    config_path = Path(__file__).parent / "src" / "config" / "models.yaml"

    # Test loading dev-fast profile
    profile = load_config_from_yaml(config_path, "dev-fast")
    print(f"\nLoaded profile: dev-fast")
    print(f"  Summarizer backend: {profile.summarizer.backend}")
    print(f"  Summarizer model: {profile.summarizer.model}")
    print(f"  HaluGate backend: {profile.halugate.backend}")
    print(f"  Overseer max_retries: {profile.overseer.max_retries}")

    assert profile.summarizer.backend == "openrouter"
    assert profile.halugate.backend == "mock"
    print("\n[PASS] dev-fast profile loaded correctly")

    # Test loading test profile
    profile = load_config_from_yaml(config_path, "test")
    print(f"\nLoaded profile: test")
    print(f"  Summarizer backend: {profile.summarizer.backend}")
    print(f"  HaluGate backend: {profile.halugate.backend}")

    assert profile.summarizer.backend == "mock"
    assert profile.halugate.backend == "mock"
    print("\n[PASS] test profile loaded correctly")

    # Test loading dev-accurate profile
    profile = load_config_from_yaml(config_path, "dev-accurate")
    print(f"\nLoaded profile: dev-accurate")
    print(f"  Summarizer backend: {profile.summarizer.backend}")
    print(f"  HaluGate backend: {profile.halugate.backend}")
    print(f"  HaluGate use_sentinel: {profile.halugate.use_sentinel}")
    print(f"  Overseer max_retries: {profile.overseer.max_retries}")
    print(f"  Overseer threshold: {profile.overseer.groundedness_threshold}")

    assert profile.summarizer.backend == "openrouter"
    assert profile.halugate.backend == "local"
    assert profile.halugate.use_sentinel is True
    assert profile.overseer.max_retries == 2
    print("\n[PASS] dev-accurate profile loaded correctly")


def test_load_config_env_fallback():
    """Test loading configuration from environment variables."""
    print("\n" + "=" * 60)
    print("TEST 2: Load configuration from environment (fallback)")
    print("=" * 60)

    from src.config.loader import load_config_from_env

    profile = load_config_from_env()
    print(f"\nLoaded from environment:")
    print(f"  Summarizer backend: {profile.summarizer.backend}")
    print(f"  HaluGate backend: {profile.halugate.backend}")
    print(f"  HaluGate use_sentinel: {profile.halugate.use_sentinel}")

    assert profile.summarizer.backend == "openrouter"
    assert profile.halugate.backend == "local"
    print("\n[PASS] Environment fallback works correctly")


def test_load_config_main():
    """Test the main load_config function."""
    print("\n" + "=" * 60)
    print("TEST 3: Main load_config function")
    print("=" * 60)

    from src.config import load_config

    # Test with explicit profile
    profile = load_config(profile="test")
    print(f"\nLoaded profile: test")
    print(f"  Summarizer: {profile.summarizer.backend}")
    print(f"  HaluGate: {profile.halugate.backend}")

    assert profile.summarizer.backend == "mock"
    print("\n[PASS] load_config with explicit profile works")

    # Test with MODEL_PROFILE env var
    original = os.environ.get("MODEL_PROFILE")
    os.environ["MODEL_PROFILE"] = "dev-fast"
    try:
        profile = load_config()
        print(f"\nLoaded from MODEL_PROFILE=dev-fast")
        print(f"  Summarizer: {profile.summarizer.backend}")
        assert profile.summarizer.backend == "openrouter"
        print("\n[PASS] load_config with MODEL_PROFILE works")
    finally:
        if original:
            os.environ["MODEL_PROFILE"] = original
        else:
            del os.environ["MODEL_PROFILE"]


def test_factory_create_summarizer():
    """Test creating summarizer from config."""
    print("\n" + "=" * 60)
    print("TEST 4: Factory - create_summarizer")
    print("=" * 60)

    from src.config import load_config, create_summarizer

    # Test mock summarizer
    profile = load_config(profile="test")
    summarizer = create_summarizer(profile.summarizer)
    print(f"\nCreated mock summarizer: {type(summarizer).__name__}")
    assert hasattr(summarizer, "complete")
    print("[PASS] Mock summarizer created")

    # Test OpenRouter summarizer (if API key available)
    if os.getenv("OPENROUTER_API_KEY"):
        profile = load_config(profile="dev-fast")
        summarizer = create_summarizer(profile.summarizer)
        print(f"Created OpenRouter summarizer: {type(summarizer).__name__}")
        print("[PASS] OpenRouter summarizer created")
    else:
        print("[SKIP] OpenRouter summarizer (no API key)")


def test_factory_create_halugate():
    """Test creating HaluGate from config."""
    print("\n" + "=" * 60)
    print("TEST 5: Factory - create_halugate")
    print("=" * 60)

    from src.config import load_config, create_halugate

    # Test mock halugate
    profile = load_config(profile="test")
    halugate = create_halugate(profile.halugate)
    print(f"\nCreated mock HaluGate: {type(halugate).__name__}")
    assert hasattr(halugate, "validate")
    print("[PASS] Mock HaluGate created")


async def test_factory_create_from_profile():
    """Test creating all backends from profile."""
    print("\n" + "=" * 60)
    print("TEST 6: Factory - create_from_profile")
    print("=" * 60)

    from src.config import load_config, create_from_profile

    profile = load_config(profile="test")
    summarizer, halugate, overseer = create_from_profile(profile)

    print(f"\nCreated from 'test' profile:")
    print(f"  Summarizer: {type(summarizer).__name__}")
    print(f"  HaluGate: {type(halugate).__name__}")
    print(f"  Overseer: {type(overseer).__name__}")

    # Test that they work together
    from src.semantic_scholar.models import PaperDetails, Author

    mock_paper = PaperDetails(
        paper_id="test123",
        title="Test Paper",
        abstract="This is a test abstract about machine learning.",
        authors=[Author(author_id="a1", name="Test Author")],
        year=2024,
        citation_count=10,
    )

    # Test mock summarizer
    async with summarizer:
        summary = await summarizer.complete("Test prompt")
        print(f"\nMock summary: {summary[:50]}...")

    # Test mock halugate
    result = await halugate.validate("context", "question", "answer")
    print(f"Mock validation: hallucination_detected={result.hallucination_detected}")

    print("\n[PASS] create_from_profile works correctly")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CONFIGURATION SYSTEM TESTS")
    print("=" * 60)

    test_load_config_from_yaml()
    test_load_config_env_fallback()
    test_load_config_main()
    test_factory_create_summarizer()
    test_factory_create_halugate()
    asyncio.run(test_factory_create_from_profile())

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
