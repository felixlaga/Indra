"""Paper deduplication logic for multi-provider search."""

import logging
from difflib import SequenceMatcher

from ..semantic_scholar.models import PaperSearchResult

logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    return title.lower().strip().replace("  ", " ")


def title_similarity(title1: str, title2: str) -> float:
    """Compute title similarity ratio (0.0 to 1.0)."""
    return SequenceMatcher(
        None,
        normalize_title(title1),
        normalize_title(title2),
    ).ratio()


def authors_overlap(paper1: PaperSearchResult, paper2: PaperSearchResult) -> bool:
    """Check if papers have overlapping authors."""
    names1 = {a.name.lower() for a in paper1.authors if a.name}
    names2 = {a.name.lower() for a in paper2.authors if a.name}

    if not names1 or not names2:
        return True  # Can't determine, assume might be same

    return bool(names1 & names2)


def _get_arxiv_id(paper: PaperSearchResult) -> str | None:
    """Extract arXiv ID from paper."""
    if paper.paper_id.startswith("arxiv:"):
        return paper.paper_id[6:]

    if hasattr(paper, "external_ids") and paper.external_ids:
        return paper.external_ids.get("ArXiv")

    return None


def _get_doi(paper: PaperSearchResult) -> str | None:
    """Extract DOI from paper."""
    if hasattr(paper, "external_ids") and paper.external_ids:
        doi = paper.external_ids.get("DOI")
        return str(doi) if doi else None
    return None


def is_duplicate(paper1: PaperSearchResult, paper2: PaperSearchResult) -> bool:
    """
    Determine if two papers are duplicates.

    Matching criteria (any one is sufficient):
    1. Same arXiv ID in external_ids or paper_id
    2. Same DOI in external_ids
    3. Title similarity > 0.9 AND same year AND overlapping authors
    """
    # Check arXiv ID match
    arxiv1 = _get_arxiv_id(paper1)
    arxiv2 = _get_arxiv_id(paper2)
    if arxiv1 and arxiv2 and arxiv1 == arxiv2:
        return True

    # Check DOI match
    doi1 = _get_doi(paper1)
    doi2 = _get_doi(paper2)
    if doi1 and doi2 and doi1 == doi2:
        return True

    # Check title + year + authors
    if paper1.title and paper2.title:
        similarity = title_similarity(paper1.title, paper2.title)
        same_year = paper1.year == paper2.year
        overlapping = authors_overlap(paper1, paper2)

        if similarity > 0.9 and same_year and overlapping:
            return True

    return False


def _should_prefer(
    new: PaperSearchResult,
    existing: PaperSearchResult,
    prefer_provider: str,
) -> bool:
    """Determine if new paper should replace existing."""
    new_is_arxiv = new.paper_id.startswith("arxiv:")
    existing_is_arxiv = existing.paper_id.startswith("arxiv:")

    if prefer_provider == "semantic_scholar":
        # Prefer SS (non-arXiv) for citation data
        if not new_is_arxiv and existing_is_arxiv:
            return True
        return False
    else:
        # Prefer arXiv for guaranteed PDFs
        if new_is_arxiv and not existing_is_arxiv:
            return True
        return False


def deduplicate_papers(
    papers: list[PaperSearchResult],
    prefer_provider: str = "semantic_scholar",
) -> list[PaperSearchResult]:
    """
    Deduplicate papers from multiple sources.

    Args:
        papers: List of papers (potentially with duplicates)
        prefer_provider: Which provider's metadata to prefer
            - "semantic_scholar": Prefer SS (has citation counts)
            - "arxiv": Prefer arXiv (has guaranteed PDF)

    Returns:
        Deduplicated list of papers
    """
    unique: list[PaperSearchResult] = []

    for paper in papers:
        is_dup = False

        for i, existing in enumerate(unique):
            if is_duplicate(paper, existing):
                is_dup = True

                # Decide which to keep based on preference
                keep_new = _should_prefer(paper, existing, prefer_provider)
                if keep_new:
                    unique[i] = paper
                    logger.debug(f"Replaced duplicate: {existing.title[:50] if existing.title else 'untitled'}")

                break

        if not is_dup:
            unique.append(paper)

    logger.info(f"Deduplicated {len(papers)} papers to {len(unique)}")
    return unique
