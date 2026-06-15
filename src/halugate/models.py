from dataclasses import dataclass


@dataclass
class HallucinationSpan:
    text: str
    start: int
    end: int
    confidence: float
    severity: int  # 0=entailment, 2=neutral, 4=contradiction


@dataclass
class HallucinationResult:
    fact_check_needed: bool
    hallucination_detected: bool
    spans: list[HallucinationSpan]
    max_severity: int
    nli_contradictions: int
    raw_response: str
