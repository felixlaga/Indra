"""Citation bridge for arXiv papers using Semantic Scholar."""

import logging
from typing import TYPE_CHECKING

from ..semantic_scholar.protocols import CitationProvider
from ..semantic_scholar.models import PaperDetails

if TYPE_CHECKING:
    from ..semantic_scholar.adapters import SemanticScholarAdapter

logger = logging.getLogger(__name__)


class ArXivCitationBridge(CitationProvider):
    """
    Provides citation data for arXiv papers via Semantic Scholar.

    arXiv has no citation API, but Semantic Scholar indexes arXiv papers
    and can look them up by arXiv ID using the format "ARXIV:2301.00001".
    """

    def __init__(self, semantic_scholar: "SemanticScholarAdapter"):
        """
        Initialize citation bridge.

        Args:
            semantic_scholar: Initialized SemanticScholarAdapter for lookups
        """
        self._ss = semantic_scholar

    def _convert_arxiv_id(self, paper_id: str) -> str:
        """Convert arXiv paper ID to Semantic Scholar format.

        Args:
            paper_id: Paper ID (e.g., "arxiv:2301.00001")

        Returns:
            Semantic Scholar format (e.g., "ARXIV:2301.00001")
        """
        if paper_id.startswith("arxiv:"):
            return f"ARXIV:{paper_id[6:]}"
        elif paper_id.startswith("arXiv:"):
            return f"ARXIV:{paper_id[6:]}"
        return paper_id  # Already in SS format or other provider

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[PaperDetails]:
        """Get papers that cite the given arXiv paper."""
        ss_id = self._convert_arxiv_id(paper_id)

        try:
            return await self._ss.get_citations(ss_id, limit=limit)
        except Exception as e:
            logger.warning(f"Failed to get citations for {paper_id}: {e}")
            return []

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[PaperDetails]:
        """Get papers referenced by the given arXiv paper."""
        ss_id = self._convert_arxiv_id(paper_id)

        try:
            return await self._ss.get_references(ss_id, limit=limit)
        except Exception as e:
            logger.warning(f"Failed to get references for {paper_id}: {e}")
            return []

    async def get_citations_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """Get citations for multiple arXiv papers."""
        ss_ids = [self._convert_arxiv_id(pid) for pid in paper_ids]
        return await self._ss.get_citations_batch(ss_ids, limit_per_paper)

    async def get_references_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """Get references for multiple arXiv papers."""
        ss_ids = [self._convert_arxiv_id(pid) for pid in paper_ids]
        return await self._ss.get_references_batch(ss_ids, limit_per_paper)
