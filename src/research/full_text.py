"""Bounded open-access PDF extraction with real page locators."""

import asyncio
import hashlib
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from .models import PaperChunk, stable_id

MAX_PDF_BYTES = 20 * 1024 * 1024


async def check_public_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Paper source must be a public HTTP(S) URL")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Paper source uses an unsupported port")
    addresses = await asyncio.get_running_loop().getaddrinfo(
        parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
    )
    if not addresses or any(
        not ipaddress.ip_address(item[4][0]).is_global for item in addresses
    ):
        raise ValueError("Paper source must not address a local or private network")


def extract_pdf(data: bytes, paper_id: str, source_url: str) -> list[PaperChunk]:
    import pymupdf

    chunks = []
    document_id = stable_id(paper_id, source_url)
    with pymupdf.open(stream=data, filetype="pdf") as document:
        if document.is_encrypted:
            raise ValueError("The open-access PDF is encrypted")
        if len(document) > 300:
            raise ValueError("PDF exceeds the 300-page research limit")
        total = 0
        for page_number, page in enumerate(document, 1):
            text = page.get_text().strip()
            total += len(text)
            if total > 1_000_000:
                raise ValueError("PDF text exceeds the research limit")
            # Never invent a section label from page number or generated text.
            for offset in range(0, len(text), 1800):
                passage = text[offset : offset + 1800].strip()
                if not passage:
                    continue
                chunks.append(
                    PaperChunk(
                        id=stable_id(
                            document_id,
                            str(page_number),
                            str(offset),
                            hashlib.sha256(passage.encode()).hexdigest(),
                        ),
                        paper_id=paper_id,
                        document_id=document_id,
                        chunk_index=len(chunks),
                        text=passage,
                        page_start=page_number,
                        page_end=page_number,
                    )
                )
    return chunks


async def fetch_full_text(paper) -> tuple[list[PaperChunk], str | None]:
    url = paper.open_access_pdf_url
    if not url:
        return [], "No open-access PDF was supplied; abstract-only coverage."
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        for _ in range(6):
            await check_public_url(url)
            async with client.stream(
                "GET", url, headers={"Accept": "application/pdf"}
            ) as response:
                if response.is_redirect:
                    url = str(response.url.join(response.headers["location"]))
                    continue
                response.raise_for_status()
                data = bytearray()
                async for part in response.aiter_bytes():
                    data.extend(part)
                    if len(data) > MAX_PDF_BYTES:
                        raise ValueError("PDF exceeds the 20 MB research limit")
                if not data.startswith(b"%PDF-"):
                    raise ValueError("Open-access source did not return a PDF")
                chunks = await asyncio.to_thread(
                    extract_pdf, bytes(data), paper.id, paper.open_access_pdf_url
                )
                return (
                    chunks,
                    None
                    if chunks
                    else "The PDF contains no extractable text; abstract-only coverage.",
                )
    raise ValueError("Too many redirects while fetching the open-access PDF")
