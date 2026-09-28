"""Trust-boundary regressions: ranking is not verification."""

import json

import httpx
import pytest

from src.claims import EvidenceCandidate, EvidenceRetriever
from src.claims.semantic_verifier import judge_passage
from src.research.full_text import extract_pdf, check_public_url
from src.research.model import ResearchModel

CASES = [
    ("ResNet outperforms ViT", "ViT outperforms ResNet"),
    (
        "The treatment reduced mortality by 45%",
        "The treatment reduced mortality by 12%",
    ),
    ("The method shows no improvement", "The method shows improvement"),
    (
        "The method improves accuracy.",
        "The method improves accuracy. The authors do not discuss costs.",
    ),
]


@pytest.mark.parametrize("claim,passage", CASES)
async def test_no_model_abstains_on_all_audit_failures(claim, passage):
    retrieved = EvidenceRetriever().retrieve(
        claim,
        [
            EvidenceCandidate(
                source_type="paper_abstract", paper_id="p1", evidence_text=passage
            )
        ],
    )
    evidence, trace = await judge_passage(claim, retrieved[0], None)
    assert evidence.relation.value == "mentions"
    assert evidence.score is None
    assert trace["strategy"] == "retrieval_only"


async def test_model_judgment_is_schema_checked_and_preserves_quote():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["provider"]["require_parameters"] is True
        assert "untrusted" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "relation": "contradicts",
                                    "quote": "ViT outperforms ResNet",
                                    "rationale": "The ordering is reversed.",
                                }
                            )
                        },
                    }
                ]
            },
        )

    model = ResearchModel(
        "fixture-key", "fixture-model", transport=httpx.MockTransport(handler)
    )
    item = EvidenceRetriever().retrieve(
        CASES[0][0],
        [
            EvidenceCandidate(
                source_type="paper_abstract", paper_id="p1", evidence_text=CASES[0][1]
            )
        ],
    )[0]
    evidence, _ = await judge_passage(CASES[0][0], item, model)
    assert evidence.relation.value == "contradicts"
    assert evidence.evidence_text == CASES[0][1]
    assert evidence.score is None


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        '{"relation":"supports","quote":"invented evidence","rationale":"unsupported"}',
    ],
)
async def test_invalid_model_output_cannot_promote_claim(content):
    model = ResearchModel(
        "fixture-key",
        "fixture-model",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": content}}
                    ]
                },
            )
        ),
    )
    item = EvidenceRetriever().retrieve(
        "The method improves accuracy.",
        [
            EvidenceCandidate(
                source_type="paper_abstract",
                paper_id="p",
                evidence_text="The method improves accuracy.",
            )
        ],
    )[0]
    with pytest.raises(ValueError):
        await judge_passage("The method improves accuracy.", item, model)


def test_pdf_chunks_preserve_real_pages():
    import pymupdf

    with pymupdf.open() as pdf:
        for text in ["First page evidence.", "Second page evidence."]:
            pdf.new_page().insert_text((72, 72), text)
        chunks = extract_pdf(pdf.tobytes(), "paper-1", "https://example.org/paper.pdf")
    assert [c.page_start for c in chunks] == [1, 2]
    assert "Second page evidence" in chunks[1].text


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/paper.pdf",
        "http://[::1]/paper.pdf",
        "http://169.254.169.254/paper.pdf",
    ],
)
async def test_pdf_fetch_blocks_local_networks(url):
    with pytest.raises(ValueError):
        await check_public_url(url)
