"""FastAPI server for HaluGate hallucination detection.

This module provides an HTTP API for the HaluGate pipeline, allowing
deployment on GPU instances (e.g., Lambda Labs A10) for faster inference.

Usage:
    HALUGATE_DEVICE=cuda uvicorn src.halugate.server:app --host 0.0.0.0 --port 8000

Environment Variables:
    HALUGATE_DEVICE: Device to run models on (cpu, cuda, mps). Default: cuda
    HALUGATE_USE_SENTINEL: Whether to use sentinel classifier. Default: true
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from .local import LocalHaluGate
from .models import HallucinationResult


class ValidateRequest(BaseModel):
    """Request body for /validate endpoint."""

    context: str
    question: str
    answer: str


class SpanResponse(BaseModel):
    """Response model for a hallucination span."""

    text: str
    start: int
    end: int
    confidence: float
    severity: int


class ValidateResponse(BaseModel):
    """Response body for /validate endpoint."""

    fact_check_needed: bool
    hallucination_detected: bool
    spans: list[SpanResponse]
    max_severity: int
    nli_contradictions: int
    raw_response: str


class HealthResponse(BaseModel):
    """Response body for /health endpoint."""

    status: str
    device: str
    use_sentinel: bool


# Global HaluGate instance
halugate: LocalHaluGate | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize HaluGate on startup."""
    global halugate

    device = os.environ.get("HALUGATE_DEVICE", "cuda")
    use_sentinel = os.environ.get("HALUGATE_USE_SENTINEL", "true").lower() == "true"

    print(f"Initializing HaluGate with device={device}, use_sentinel={use_sentinel}")
    halugate = LocalHaluGate(device=device, use_sentinel=use_sentinel)
    print("HaluGate initialized successfully")

    yield

    # Cleanup (if needed)
    halugate = None


app = FastAPI(
    title="HaluGate API",
    description="Hallucination detection service using 3-stage pipeline",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/validate", response_model=ValidateResponse)
async def validate(req: ValidateRequest) -> ValidateResponse:
    """Run hallucination detection on the provided context, question, and answer.

    Args:
        req: Validation request containing context, question, and answer

    Returns:
        Validation result with detected hallucination spans and severity scores
    """
    if halugate is None:
        raise RuntimeError("HaluGate not initialized")

    result: HallucinationResult = await halugate.validate(
        req.context, req.question, req.answer
    )

    return ValidateResponse(
        fact_check_needed=result.fact_check_needed,
        hallucination_detected=result.hallucination_detected,
        spans=[
            SpanResponse(
                text=s.text,
                start=s.start,
                end=s.end,
                confidence=s.confidence,
                severity=s.severity,
            )
            for s in result.spans
        ],
        max_severity=result.max_severity,
        nli_contradictions=result.nli_contradictions,
        raw_response=result.raw_response,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Check service health and report configuration."""
    if halugate is None:
        return HealthResponse(
            status="not_initialized",
            device="unknown",
            use_sentinel=False,
        )

    return HealthResponse(
        status="ok",
        device=halugate.device,
        use_sentinel=halugate.use_sentinel,
    )
