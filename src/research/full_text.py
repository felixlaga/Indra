"""Bounded open-access PDF extraction with real page locators."""

import asyncio
import hashlib
import ipaddress
import shutil
import socket
from urllib.parse import urlparse

import httpx

from .models import PaperChunk, stable_id

MAX_PDF_BYTES = 20 * 1024 * 1024
# OCR takes about a second per page; cap it so one scanned book cannot stall a branch.
MAX_OCR_PAGES = 40


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


def ocr_available() -> bool:
    """PyMuPDF's OCR uses an installed Tesseract (for example `brew install tesseract`)."""

    return shutil.which("tesseract") is not None


def _ocr_text(page) -> str:
    textpage = page.get_textpage_ocr(dpi=200, full=True)
    return page.get_text(textpage=textpage)


def extract_pdf(
    data: bytes, paper_id: str, source_url: str, report: dict | None = None
) -> list[PaperChunk]:
    """Page-numbered passages; pages without a text layer are OCR'd when possible.

    ``report`` receives counts of scanned pages found and pages read with OCR.
    """

    import pymupdf

    report = report if report is not None else {}
    report.update(scanned=0, ocr=0)
    can_ocr = ocr_available()

    chunks = []
    document_id = stable_id(paper_id, source_url)
    with pymupdf.open(stream=data, filetype="pdf") as document:
        if document.is_encrypted:
            raise ValueError("The open-access PDF is encrypted")
        if len(document) > 300:
            raise ValueError("PDF exceeds the 300-page research limit")
        total = 0
        for page_number, page in enumerate(document, 1):
            # PDFs can embed NUL characters, which PostgreSQL text cannot store.
            text = page.get_text().replace("\x00", "").strip()
            if not text and page.get_images():
                report["scanned"] += 1
                if can_ocr and report["ocr"] < MAX_OCR_PAGES:
                    text = _ocr_text(page).replace("\x00", "").strip()
                    report["ocr"] += 1
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
                report: dict = {}
                chunks = await asyncio.to_thread(
                    extract_pdf, bytes(data), paper.id, paper.open_access_pdf_url, report
                )
                return chunks, scan_note(chunks, report)
    raise ValueError("Too many redirects while fetching the open-access PDF")


def scan_note(chunks, report: dict) -> str | None:
    """Explain OCR use or why scanned pages were skipped."""

    notes = []
    if report.get("ocr"):
        notes.append(
            f"{report['ocr']} scanned page(s) were read with OCR; OCR text can contain recognition errors."
        )
    skipped = report.get("scanned", 0) - report.get("ocr", 0)
    if skipped:
        reason = (
            "the OCR page limit was reached"
            if ocr_available()
            else "OCR needs Tesseract installed"
        )
        notes.append(f"{skipped} scanned page(s) were not read because {reason}.")
    if not chunks:
        notes.insert(0, "The PDF contains no extractable text; abstract-only coverage.")
    return " ".join(notes) or None
