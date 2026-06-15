"""
HaluGate Local Integration Test

Tests the pure Python HaluGate implementation with all 3 stages:
1. Sentinel: Fact-check classifier
2. Detector: Token-level hallucination detection (LettuceDetect)
3. Explainer: NLI-based verification
"""

import asyncio

from src.halugate import LocalHaluGate


async def test_local_halugate():
    print("Loading HaluGate models (3 stages)...")
    detector = LocalHaluGate(use_sentinel=True)
    print("Models loaded!\n")

    # Test 1: Factual query with hallucination
    print("=" * 50)
    print("Test 1: Factual query with hallucination")
    print("=" * 50)

    context = "The Eiffel Tower was built in 1887-1889 and is 330 meters tall."
    question = "When was the Eiffel Tower built?"
    answer = "The Eiffel Tower was built in 1950 and is 500 meters tall."

    result = await detector.validate(context, question, answer)

    print(f"Fact-check needed: {result.fact_check_needed}")
    print(f"Hallucination detected: {result.hallucination_detected}")
    print(f"Hallucinated spans: {[s.text for s in result.spans]}")
    print(f"Max severity: {result.max_severity} (4=contradiction, 2=neutral)")
    print(f"NLI contradictions: {result.nli_contradictions}")
    print(f"Groundedness: {detector.compute_groundedness(result, answer):.2%}")

    assert result.fact_check_needed, "Sentinel should flag factual query"

    # Test 2: Accurate answer (no hallucination)
    print("\n" + "=" * 50)
    print("Test 2: Accurate answer (no hallucination expected)")
    print("=" * 50)

    accurate_answer = "The Eiffel Tower was built in 1887-1889 and is 330 meters tall."
    result2 = await detector.validate(context, question, accurate_answer)

    print(f"Fact-check needed: {result2.fact_check_needed}")
    print(f"Hallucination detected: {result2.hallucination_detected}")
    print(f"Hallucinated spans: {[s.text for s in result2.spans]}")
    print(f"Groundedness: {detector.compute_groundedness(result2, accurate_answer):.2%}")

    # Test 3: Creative query (should skip detection if sentinel works)
    print("\n" + "=" * 50)
    print("Test 3: Creative query (may skip detection)")
    print("=" * 50)

    creative_q = "Write a poem about the sunset"
    result3 = await detector.validate("", creative_q, "The sun sets golden...")

    print(f"Fact-check needed: {result3.fact_check_needed}")
    print(f"Hallucination detected: {result3.hallucination_detected}")

    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_local_halugate())
