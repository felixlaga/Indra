"""HTTP client for remote HaluGate service.

This module provides an HTTP client that implements the same interface as
LocalHaluGate, allowing transparent switching between local and remote
hallucination detection.

Usage:
    from src.halugate import HTTPHaluGate

    halugate = HTTPHaluGate("http://localhost:8000")
    result = await halugate.validate(context, question, answer)
"""

import httpx

from .models import HallucinationResult, HallucinationSpan


class HTTPHaluGate:
    """HTTP client for remote HaluGate service.

    This client implements the same interface as LocalHaluGate, allowing
    transparent switching between local and remote hallucination detection.
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        """Initialize HTTP client.

        Args:
            base_url: Base URL of the HaluGate service (e.g., http://localhost:8000)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def validate(
        self,
        context: str,
        question: str,
        answer: str,
    ) -> HallucinationResult:
        """Validate an answer for hallucinations.

        Args:
            context: Source text to verify against
            question: The original query
            answer: The LLM-generated response to validate

        Returns:
            HallucinationResult with detected spans and severity scores
        """
        client = await self._get_client()

        response = await client.post(
            f"{self.base_url}/validate",
            json={"context": context, "question": question, "answer": answer},
        )
        response.raise_for_status()
        data = response.json()

        return HallucinationResult(
            fact_check_needed=data["fact_check_needed"],
            hallucination_detected=data["hallucination_detected"],
            spans=[
                HallucinationSpan(
                    text=s["text"],
                    start=s["start"],
                    end=s["end"],
                    confidence=s["confidence"],
                    severity=s["severity"],
                )
                for s in data["spans"]
            ],
            max_severity=data["max_severity"],
            nli_contradictions=data["nli_contradictions"],
            raw_response=data["raw_response"],
        )

    def compute_groundedness(self, result: HallucinationResult, answer: str) -> float:
        """Calculate % of answer that is grounded (not hallucinated).

        Args:
            result: HallucinationResult from validate()
            answer: Original answer text

        Returns:
            Float between 0.0 and 1.0 representing groundedness
        """
        if not result.spans:
            return 1.0
        hallucinated_chars = sum(len(s.text) for s in result.spans)
        return 1.0 - (hallucinated_chars / len(answer)) if answer else 1.0

    async def health(self) -> dict:
        """Check service health.

        Returns:
            Health status dict with 'status', 'device', and 'use_sentinel' keys
        """
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        await self.close()
