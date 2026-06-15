"""
Pure Python HaluGate - Full 3-stage hallucination detection pipeline.

Replaces the Docker-based vLLM Semantic Router with direct model inference:
1. Sentinel: Fact-check classifier (should we verify this query?)
2. Detector: Token-level hallucination detection (LettuceDetect)
3. Explainer: NLI-based verification (is the span contradicted by context?)
"""

from lettucedetect.models.inference import HallucinationDetector
from transformers import pipeline

from .models import HallucinationResult, HallucinationSpan


class LocalHaluGate:
    """
    Pure Python HaluGate - Full 3-stage pipeline:
    1. Sentinel: Fact-check classifier
    2. Detector: Token-level hallucination detection (LettuceDetect)
    3. Explainer: NLI-based verification
    """

    def __init__(self, device: str = "cpu", use_sentinel: bool = True):
        self.device = device
        self.use_sentinel = use_sentinel

        # Stage 1: Sentinel (fact-check classifier)
        if use_sentinel:
            self.sentinel = pipeline(
                "text-classification",
                model="LLM-Semantic-Router/halugate-sentinel",
                device=device,
            )

        # Stage 2: Detector (LettuceDetect - token-level)
        self.detector = HallucinationDetector(
            method="transformer",
            model_path="KRLabsOrg/lettucedect-base-modernbert-en-v1",
        )

        # Stage 3: Explainer (NLI)
        self.nli = pipeline(
            "text-classification",
            model="tasksource/ModernBERT-base-nli",
            device=device,
        )

    def _needs_fact_check(self, question: str) -> tuple[bool, float]:
        """Stage 1: Determine if query needs fact-checking."""
        if not self.use_sentinel:
            return True, 1.0

        result = self.sentinel(question)[0]
        # Sentinel labels: FACT_CHECK_NEEDED (1) or NO_FACT_CHECK_NEEDED (0)
        needs_check = result["label"] == "LABEL_1" or "FACT_CHECK" in result["label"].upper()
        return needs_check, result["score"]

    async def validate(
        self,
        context: str,
        question: str,
        answer: str,
    ) -> HallucinationResult:
        """
        Run the full HaluGate pipeline.

        Args:
            context: Source text (e.g., paper abstracts) to verify against
            question: The original query
            answer: The LLM-generated response to validate

        Returns:
            HallucinationResult with detected spans and severity scores
        """
        # Stage 1: Sentinel - should we fact-check?
        fact_check_needed, sentinel_confidence = self._needs_fact_check(question)

        if not fact_check_needed:
            return HallucinationResult(
                fact_check_needed=False,
                hallucination_detected=False,
                spans=[],
                max_severity=0,
                nli_contradictions=0,
                raw_response=f"Sentinel: no fact-check needed (conf={sentinel_confidence:.2f})",
            )

        # Stage 2: Detector - find hallucinated spans
        raw_spans = self.detector.predict(
            context=[context],
            question=question,
            answer=answer,
            output_format="spans",
        )

        # Stage 3: Explainer - verify each span with NLI
        spans = []
        nli_contradictions = 0
        max_severity = 0

        for span in raw_spans:
            # Run NLI: is this span contradicted/neutral/entailed by context?
            nli_input = f"{context} [SEP] {span['text']}"
            nli_result = self.nli(nli_input)[0]

            label = nli_result["label"].upper()
            severity = {"ENTAILMENT": 0, "NEUTRAL": 2, "CONTRADICTION": 4}.get(label, 2)

            # Filter false positives (entailed spans are supported by context)
            if severity == 0:
                continue

            if severity == 4:
                nli_contradictions += 1
            max_severity = max(max_severity, severity)

            spans.append(
                HallucinationSpan(
                    text=span["text"],
                    start=span["start"],
                    end=span["end"],
                    confidence=span["confidence"],
                    severity=severity,
                )
            )

        return HallucinationResult(
            fact_check_needed=True,
            hallucination_detected=len(spans) > 0,
            spans=spans,
            max_severity=max_severity,
            nli_contradictions=nli_contradictions,
            raw_response="",
        )

    def compute_groundedness(self, result: HallucinationResult, answer: str) -> float:
        """Calculate % of answer that is grounded (not hallucinated)."""
        if not result.spans:
            return 1.0
        hallucinated_chars = sum(len(s.text) for s in result.spans)
        return 1.0 - (hallucinated_chars / len(answer)) if answer else 1.0
