"""OpenAlex search and citation lookups (https://docs.openalex.org).

OpenAlex is free and needs no key. Setting ``INDRA_CONTACT_EMAIL`` sends it as
``mailto`` so requests use OpenAlex's faster, more reliable "polite pool".
"""

from __future__ import annotations

import calendar
import os
import re

import httpx

from ..api.models import Paper
from ..api.repository import utc_now
from ..domain.papers import PaperExternalIds, canonical_paper_key, normalize_doi
from .models import stable_id

BASE_URL = "https://api.openalex.org"
CONTACT_EMAIL_ENV = "INDRA_CONTACT_EMAIL"
# OpenAlex accepts up to 50 values in one OR filter.
MAX_LOOKUP = 50
_FIELDS = (
    "id,doi,title,display_name,publication_year,authorships,primary_location,"
    "best_oa_location,open_access,cited_by_count,referenced_works,abstract_inverted_index"
)
_ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(.+)$")


def short_id(value: str | None) -> str | None:
    """"https://openalex.org/W123" → "W123"."""

    return value.rsplit("/", 1)[-1] if value else None


def abstract_text(inverted: dict | None) -> str | None:
    """Rebuild an abstract from OpenAlex's word → positions index."""

    if not inverted:
        return None
    positions = sorted((p, word) for word, places in inverted.items() for p in places)
    return " ".join(word for _, word in positions) or None


def to_product_paper(work: dict) -> Paper:
    doi = normalize_doi(work.get("doi"))
    arxiv_id = None
    if doi and (match := _ARXIV_DOI.match(doi)):
        # arXiv's DataCite DOI identifies the same preprint the arXiv source returns.
        arxiv_id, doi = match.group(1), None
    openalex_id = short_id(work.get("id"))
    external = PaperExternalIds(doi=doi, arxiv_id=arxiv_id, openalex_id=openalex_id)
    title = work.get("title") or work.get("display_name") or "Untitled paper"
    year = work.get("publication_year")
    key = canonical_paper_key(external, title, year)
    source = ((work.get("primary_location") or {}).get("source") or {})
    oa = work.get("best_oa_location") or {}
    now = utc_now()
    return Paper(
        id=stable_id(key),
        canonical_key=key,
        title=title,
        abstract=abstract_text(work.get("abstract_inverted_index")),
        doi=external.doi,
        arxiv_id=external.arxiv_id,
        openalex_id=openalex_id,
        year=year,
        venue=source.get("display_name"),
        citation_count=work.get("cited_by_count"),
        reference_count=len(work.get("referenced_works") or []) or None,
        authors=[
            {
                "name": (a.get("author") or {}).get("display_name"),
                "author_id": short_id((a.get("author") or {}).get("id")),
            }
            for a in work.get("authorships") or []
            if (a.get("author") or {}).get("display_name")
        ],
        url=work.get("doi") or work.get("id"),
        open_access_pdf_url=oa.get("pdf_url"),
        metadata={
            "provider": "openalex",
            "references": [short_id(w) for w in work.get("referenced_works") or []],
        },
        created_at=now,
        updated_at=now,
    )


def _full_date(value: str, *, end: bool) -> str:
    """Expand "2023" or "2023-06" to the first or last day of that period."""

    parts = value.split("-")
    if len(parts) == 1:
        return f"{value}-12-31" if end else f"{value}-01-01"
    if len(parts) == 2:
        year, month = int(parts[0]), int(parts[1])
        day = calendar.monthrange(year, month)[1] if end else 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    return value


def _filters(filters: dict) -> str | None:
    start, end = filters.get("start_date"), filters.get("end_date")
    if not (start or end) and filters.get("year"):
        start, _, end = str(filters["year"]).partition("-")
        end = end or start
    parts = []
    if start:
        parts.append(f"from_publication_date:{_full_date(start, end=False)}")
    if end:
        parts.append(f"to_publication_date:{_full_date(end, end=True)}")
    if filters.get("min_citation_count") is not None:
        parts.append(f"cited_by_count:>{int(filters['min_citation_count']) - 1}")
    if filters.get("open_access_only"):
        parts.append("open_access.is_oa:true")
    return ",".join(parts) or None


class OpenAlexClient:
    def __init__(self, *, transport=None, timeout=30.0, email=None):
        self.email = email if email is not None else os.getenv(CONTACT_EMAIL_ENV, "")
        self._client = httpx.AsyncClient(
            base_url=BASE_URL, timeout=timeout, transport=transport
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self._client.aclose()

    async def _works(self, params: dict) -> list[dict]:
        params = {**params, "select": _FIELDS}
        if self.email:
            params["mailto"] = self.email
        response = await self._client.get("/works", params=params)
        response.raise_for_status()
        return response.json().get("results") or []

    async def search(self, query: str, *, limit: int, filters: dict | None = None) -> list[Paper]:
        params = {"search": query, "per-page": str(max(1, min(limit, 50)))}
        if filter_value := _filters(filters or {}):
            params["filter"] = filter_value
        return [to_product_paper(w) for w in await self._works(params) if w.get("title")]

    async def works(self, ids: list[str]) -> list[Paper]:
        """Works by OpenAlex ID ("W123"), in batches of the OR-filter limit."""

        found: list[Paper] = []
        for start in range(0, len(ids), MAX_LOOKUP):
            batch = ids[start : start + MAX_LOOKUP]
            works = await self._works(
                {"filter": "ids.openalex:" + "|".join(batch), "per-page": str(len(batch))}
            )
            found.extend(to_product_paper(w) for w in works if w.get("title"))
        return found

    async def citing(self, ids: list[str], *, limit: int, sort: str) -> list[Paper]:
        """Works that cite any of ``ids``, e.g. sorted by "cited_by_count:desc"."""

        if not ids:
            return []
        params = {
            "filter": "cites:" + "|".join(ids[:MAX_LOOKUP]),
            "per-page": str(max(1, min(limit, 200))),
            "sort": sort,
        }
        return [to_product_paper(w) for w in await self._works(params) if w.get("title")]

    async def lookup(self, papers: list[Paper]) -> dict[str, Paper]:
        """OpenAlex records for papers, keyed by the paper's canonical key.

        Matches by OpenAlex ID, DOI, or arXiv's DOI for preprints.
        """

        wanted: dict[str, str] = {}
        for paper in papers:
            if paper.openalex_id:
                wanted[f"openalex:{paper.openalex_id.lower()}"] = paper.canonical_key
            if paper.doi:
                wanted[f"doi:{normalize_doi(paper.doi)}"] = paper.canonical_key
            if paper.arxiv_id:
                wanted[f"doi:10.48550/arxiv.{paper.arxiv_id.lower()}"] = paper.canonical_key
        ids = [k.split(":", 1)[1] for k in wanted if k.startswith("openalex:")]
        dois = [k.split(":", 1)[1] for k in wanted if k.startswith("doi:")]
        found: dict[str, Paper] = {}
        for field, values in (("ids.openalex", ids), ("doi", dois)):
            for start in range(0, len(values), MAX_LOOKUP):
                batch = values[start : start + MAX_LOOKUP]
                works = await self._works(
                    {"filter": f"{field}:" + "|".join(batch), "per-page": str(len(batch))}
                )
                for work in works:
                    keys = [f"openalex:{(short_id(work.get('id')) or '').lower()}"]
                    if work.get("doi"):
                        keys.append(f"doi:{normalize_doi(work['doi'])}")
                    for key in keys:
                        if key in wanted:
                            found[wanted[key]] = to_product_paper(work)
        return found
