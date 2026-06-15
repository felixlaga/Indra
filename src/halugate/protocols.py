from typing import Protocol

from .models import HallucinationResult


class HallucinationDetectorProtocol(Protocol):
    async def validate(
        self,
        context: str,
        question: str,
        answer: str,
    ) -> HallucinationResult: ...

    def compute_groundedness(
        self,
        result: HallucinationResult,
        answer: str,
    ) -> float: ...
