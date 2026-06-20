"""Deterministic Phase 8 research-artifact generation.

Exports use only durable session state. Claim status is always preserved in claim-
bearing artifacts, and unsupported or speculative claims are explicitly labelled.
"""

from __future__ import annotations

from collections import defaultdict
import csv
from io import StringIO
import json
import re
from typing import Any

from ..analysis import ResearchAdviceBuilder
from ..maps import ResearchMapBuilder
from .models import ExportArtifact, ExportCatalog, ExportDescriptor


_FORMATS = {
    "bibtex": ExportDescriptor(
        format="bibtex",
        label="BibTeX bibliography",
        filename="erla-bibliography.bib",
        media_type="application/x-bibtex; charset=utf-8",
        description="Session papers as BibTeX records.",
    ),
    "ris": ExportDescriptor(
        format="ris",
        label="RIS bibliography",
        filename="erla-bibliography.ris",
        media_type="application/x-research-info-systems; charset=utf-8",
        description="Session papers in RIS format.",
    ),
    "report-markdown": ExportDescriptor(
        format="report-markdown",
        label="Markdown research report",
        filename="erla-research-report.md",
        media_type="text/markdown; charset=utf-8",
        description="Research report with papers, findings, uncertainty, and next actions.",
    ),
    "literature-review-latex": ExportDescriptor(
        format="literature-review-latex",
        label="LaTeX literature review outline",
        filename="erla-literature-review.tex",
        media_type="application/x-tex; charset=utf-8",
        description="LaTeX outline grounded in session branches and claim status.",
    ),
    "annotated-bibliography": ExportDescriptor(
        format="annotated-bibliography",
        label="Annotated bibliography",
        filename="erla-annotated-bibliography.md",
        media_type="text/markdown; charset=utf-8",
        description="Paper annotations with linked claim validation states.",
    ),
    "claim-ledger-csv": ExportDescriptor(
        format="claim-ledger-csv",
        label="Claim ledger CSV",
        filename="erla-claim-ledger.csv",
        media_type="text/csv; charset=utf-8",
        description="Flat claim ledger with evidence counts and validation status.",
    ),
    "claim-ledger-json": ExportDescriptor(
        format="claim-ledger-json",
        label="Claim ledger JSON",
        filename="erla-claim-ledger.json",
        media_type="application/json; charset=utf-8",
        description="Structured claims and attached evidence passages.",
    ),
    "research-map-json": ExportDescriptor(
        format="research-map-json",
        label="Research map JSON",
        filename="erla-research-map.json",
        media_type="application/json; charset=utf-8",
        description="Citation graph, timeline, clusters, recommendations, and overview.",
    ),
}


class ExportGenerator:
    """Generate all Phase 8 session artifacts."""

    def __init__(self) -> None:
        self._map_builder = ResearchMapBuilder()
        self._advice_builder = ResearchAdviceBuilder()

    def catalog(self, session_id: str) -> ExportCatalog:
        return ExportCatalog(session_id=session_id, artifacts=list(_FORMATS.values()))

    def generate(self, snapshot: Any, format_name: str) -> ExportArtifact:
        descriptor = _FORMATS.get(format_name)
        if descriptor is None:
            raise ValueError(f"Unsupported export format: {format_name}")
        builders = {
            "bibtex": self._bibtex,
            "ris": self._ris,
            "report-markdown": self._markdown_report,
            "literature-review-latex": self._latex_outline,
            "annotated-bibliography": self._annotated_bibliography,
            "claim-ledger-csv": self._claim_ledger_csv,
            "claim-ledger-json": self._claim_ledger_json,
            "research-map-json": self._research_map_json,
        }
        content = builders[format_name](snapshot)
        return ExportArtifact(
            format=format_name,
            filename=descriptor.filename,
            media_type=descriptor.media_type,
            content=content,
        )

    def _bibtex(self, snapshot: Any) -> str:
        records = []
        used: set[str] = set()
        for entry in snapshot.papers:
            paper = entry.paper
            key = self._citation_key(paper, used)
            fields = {
                "title": self._bib_escape(paper.title),
                "author": " and ".join(self._author_names(paper.authors)),
                "year": str(paper.year) if paper.year else None,
                "journal": paper.venue,
                "doi": paper.doi,
                "eprint": paper.arxiv_id,
                "url": paper.url or paper.open_access_pdf_url or paper.pdf_url,
                "abstract": self._bib_escape(paper.abstract) if paper.abstract else None,
                "note": "Exported from ERLA; inspect claim ledger for validation status.",
            }
            lines = [f"@article{{{key},"]
            for name, value in fields.items():
                if value:
                    lines.append(f"  {name} = {{{value}}},")
            lines.append("}")
            records.append("\n".join(lines))
        return "\n\n".join(records) + ("\n" if records else "")

    def _ris(self, snapshot: Any) -> str:
        records = []
        for entry in snapshot.papers:
            paper = entry.paper
            lines = ["TY  - JOUR", f"TI  - {paper.title}"]
            for author in self._author_names(paper.authors):
                lines.append(f"AU  - {author}")
            if paper.year:
                lines.append(f"PY  - {paper.year}")
            if paper.venue:
                lines.append(f"JO  - {paper.venue}")
            if paper.doi:
                lines.append(f"DO  - {paper.doi}")
            if paper.url or paper.open_access_pdf_url or paper.pdf_url:
                lines.append(f"UR  - {paper.url or paper.open_access_pdf_url or paper.pdf_url}")
            if paper.abstract:
                lines.append(f"AB  - {self._single_line(paper.abstract)}")
            lines.append("N1  - Exported from ERLA; validation status is stored in the claim ledger.")
            lines.append("ER  -")
            records.append("\n".join(lines))
        return "\n\n".join(records) + ("\n" if records else "")

    def _markdown_report(self, snapshot: Any) -> str:
        research_map = self._map_builder.build(snapshot)
        advice = self._advice_builder.build(snapshot, research_map)
        branch_by_id = {str(branch.id): branch for branch in snapshot.branches}
        claims_by_branch: dict[str, list[Any]] = defaultdict(list)
        for claim in snapshot.claims:
            claims_by_branch[str(claim.branch_id or "unassigned")].append(claim)

        lines = [
            f"# ERLA research report: {snapshot.session.initial_query}",
            "",
            "> Validation notice: every claim below includes its current ERLA status. "
            "Unsupported, contradicted, speculative, and unreviewed claims must not be read as established facts.",
            "",
            "## Field overview",
            "",
            research_map.overview.text,
            "",
            f"- Papers: {len(snapshot.papers)}",
            f"- Branches: {len(snapshot.branches)}",
            f"- Claims: {len(snapshot.claims)}",
            f"- Observed citation paths: {research_map.overview.observed_citation_edge_count}",
            "",
            "## Branch synthesis",
            "",
        ]
        for synthesis in research_map.branch_syntheses:
            lines.extend([
                f"### {synthesis.label}",
                "",
                f"**Source:** `{synthesis.source}`  ",
                f"**Validation:** `{synthesis.validation_status or 'not_available'}`",
                "",
                synthesis.text,
                "",
            ])
            for claim in claims_by_branch.get(synthesis.branch_id, []):
                lines.append(self._claim_markdown(claim))
            lines.append("")

        lines.extend(["## Papers", ""])
        for entry in snapshot.papers:
            paper = entry.paper
            lines.extend([
                f"### {paper.title}",
                "",
                f"- Authors: {', '.join(self._author_names(paper.authors)) or 'Unknown'}",
                f"- Year: {paper.year or 'Unknown'}",
                f"- Venue: {paper.venue or 'Unknown'}",
                f"- DOI: {paper.doi or '—'}",
                f"- Selection reason: {entry.selection_reason or 'Not recorded'}",
                "",
                paper.abstract or "No abstract was persisted.",
                "",
            ])

        lines.extend(["## Contradictions and weak evidence", ""])
        if not advice.contradictions and not advice.weak_evidence:
            lines.append("No contradiction or weak-evidence signals were detected in the current session state.")
        for item in advice.contradictions:
            lines.append(f"- **{item.status.upper()}** — {item.description} ({item.rationale})")
        for item in advice.weak_evidence:
            lines.append(f"- **{item.claim_status.upper()}** — {item.claim_text} ({item.reason})")
        lines.extend(["", "## Research directions", ""])
        for recommendation in advice.recommendations:
            lines.append(f"- **{recommendation.priority.upper()}: {recommendation.title}** — {recommendation.action}")
        lines.extend(["", "## Speculative hypotheses", ""])
        if not advice.hypotheses:
            lines.append("No hypothesis proposals were generated.")
        for hypothesis in advice.hypotheses:
            lines.extend([
                f"### [SPECULATIVE] {hypothesis.text}",
                "",
                f"Confidence signal: {hypothesis.confidence:.2f}; testability signal: {hypothesis.testability:.2f}; risk: {hypothesis.risk}.",
                "",
                "Missing evidence:",
                *[f"- {item}" for item in hypothesis.missing_evidence],
                "",
                "Next steps:",
                *[f"1. {item}" for item in hypothesis.next_steps],
                "",
            ])
        return "\n".join(lines).rstrip() + "\n"

    def _latex_outline(self, snapshot: Any) -> str:
        research_map = self._map_builder.build(snapshot)
        advice = self._advice_builder.build(snapshot, research_map)
        lines = [
            r"\documentclass[11pt]{article}",
            r"\usepackage[margin=1in]{geometry}",
            r"\usepackage{hyperref}",
            r"\usepackage{xcolor}",
            r"\newcommand{\claimstatus}[1]{\texttt{[#1]}}",
            r"\title{" + self._latex_escape(snapshot.session.initial_query) + r"}",
            r"\author{ERLA export}",
            r"\date{}",
            r"\begin{document}",
            r"\maketitle",
            r"\begin{quote}\textbf{Validation notice.} Claim statuses are preserved. Unsupported or speculative claims are not established facts.\end{quote}",
            r"\section{Field overview}",
            self._latex_escape(research_map.overview.text),
            r"\section{Literature landscape}",
        ]
        for cluster in research_map.clusters:
            lines.append(r"\subsection{" + self._latex_escape(cluster.label) + "}")
            for paper_id in cluster.paper_ids:
                node = next((node for node in research_map.nodes if node.paper_id == paper_id), None)
                if node:
                    lines.append(
                        r"\paragraph{" + self._latex_escape(node.title) + "} "
                        + self._latex_escape(
                            f"Year: {node.year or 'unknown'}; role: {node.role}; citations: {node.citation_count}."
                        )
                    )
        lines.append(r"\section{Validated findings and unresolved claims}")
        for claim in snapshot.claims:
            lines.append(
                r"\paragraph{\claimstatus{" + self._latex_escape(self._value(claim.status)) + "}} "
                + self._latex_escape(claim.claim_text)
            )
        lines.append(r"\section{Contradictions and evidence gaps}")
        for item in advice.contradictions:
            lines.append(r"\paragraph{" + self._latex_escape(item.status) + "} " + self._latex_escape(item.description))
        for gap in advice.gaps:
            lines.append(r"\paragraph{" + self._latex_escape(gap.title) + "} " + self._latex_escape(gap.description + " " + gap.caveat))
        lines.append(r"\section{Research directions}")
        lines.append(r"\begin{itemize}")
        for recommendation in advice.recommendations:
            lines.append(r"\item " + self._latex_escape(recommendation.title + ": " + recommendation.action))
        lines.append(r"\end{itemize}")
        lines.append(r"\section{Speculative hypotheses}")
        for hypothesis in advice.hypotheses:
            lines.append(
                r"\paragraph{SPECULATIVE} " + self._latex_escape(hypothesis.text)
                + r"\\ \textit{This proposal is not validated and does not claim novelty.}"
            )
        lines.extend([r"\bibliographystyle{plain}", r"\bibliography{erla-bibliography}", r"\end{document}"])
        return "\n".join(lines) + "\n"

    def _annotated_bibliography(self, snapshot: Any) -> str:
        claims_by_paper: dict[str, list[Any]] = defaultdict(list)
        evidence_by_claim: dict[str, list[Any]] = defaultdict(list)
        for claim in snapshot.claims:
            if claim.paper_id:
                claims_by_paper[str(claim.paper_id)].append(claim)
        for evidence in snapshot.claim_evidence:
            evidence_by_claim[str(evidence.claim_id)].append(evidence)
        lines = [
            "# ERLA annotated bibliography",
            "",
            "> Claim annotations preserve validation status. Labels such as `NOT_FOUND`, `CONTRADICTED`, `SPECULATIVE`, and `NEEDS_REVIEW` indicate that the statement is not established.",
            "",
        ]
        for entry in snapshot.papers:
            paper = entry.paper
            lines.extend([
                f"## {paper.title}",
                "",
                f"**Citation:** {', '.join(self._author_names(paper.authors)) or 'Unknown author'} ({paper.year or 'n.d.'}). {paper.title}. {paper.venue or ''}",
                "",
                f"**Why included:** {entry.selection_reason or 'No selection rationale was persisted.'}",
                "",
                f"**Abstract:** {paper.abstract or 'No abstract was persisted.'}",
                "",
                "**Claim annotations:**",
                "",
            ])
            paper_claims = claims_by_paper.get(str(paper.id), [])
            if not paper_claims:
                lines.append("- No claims have been extracted for this paper.")
            for claim in paper_claims:
                status = self._value(claim.status).upper()
                evidence_count = len(evidence_by_claim.get(str(claim.id), []))
                lines.append(f"- **[{status}]** {claim.claim_text} _(evidence passages: {evidence_count})_")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _claim_ledger_csv(self, snapshot: Any) -> str:
        evidence_by_claim: dict[str, list[Any]] = defaultdict(list)
        for evidence in snapshot.claim_evidence:
            evidence_by_claim[str(evidence.claim_id)].append(evidence)
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "claim_id", "claim_text", "claim_type", "status", "confidence",
                "supported_for_synthesis", "branch_id", "paper_id", "summary_id",
                "evidence_count", "evidence_relations", "created_by", "created_at",
            ],
        )
        writer.writeheader()
        for claim in snapshot.claims:
            evidence = evidence_by_claim.get(str(claim.id), [])
            status = self._value(claim.status)
            writer.writerow({
                "claim_id": claim.id,
                "claim_text": claim.claim_text,
                "claim_type": self._value(claim.claim_type),
                "status": status,
                "confidence": claim.confidence if claim.confidence is not None else "",
                "supported_for_synthesis": status in {"supported", "weakly_supported"},
                "branch_id": claim.branch_id or "",
                "paper_id": claim.paper_id or "",
                "summary_id": claim.summary_id or "",
                "evidence_count": len(evidence),
                "evidence_relations": "|".join(self._value(item.relation) for item in evidence),
                "created_by": claim.created_by or "",
                "created_at": claim.created_at.isoformat(),
            })
        return output.getvalue()

    def _claim_ledger_json(self, snapshot: Any) -> str:
        evidence_by_claim: dict[str, list[Any]] = defaultdict(list)
        for evidence in snapshot.claim_evidence:
            evidence_by_claim[str(evidence.claim_id)].append(evidence)
        payload = {
            "session_id": str(snapshot.session.id),
            "validation_notice": (
                "Only supported and weakly_supported claims are eligible for cautious synthesis. "
                "All other statuses remain unsupported, contradicted, speculative, or unreviewed."
            ),
            "claims": [
                {
                    **claim.model_dump(mode="json"),
                    "supported_for_synthesis": self._value(claim.status)
                    in {"supported", "weakly_supported"},
                    "evidence": [item.model_dump(mode="json") for item in evidence_by_claim.get(str(claim.id), [])],
                }
                for claim in snapshot.claims
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    def _research_map_json(self, snapshot: Any) -> str:
        research_map = self._map_builder.build(snapshot)
        return json.dumps(research_map.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"

    def _claim_markdown(self, claim: Any) -> str:
        status = self._value(claim.status).upper()
        prefix = "SUPPORTED" if status == "SUPPORTED" else status
        return f"- **[{prefix}]** {claim.claim_text}"

    def _citation_key(self, paper: Any, used: set[str]) -> str:
        authors = self._author_names(paper.authors)
        surname = re.sub(r"[^A-Za-z0-9]", "", (authors[0].split()[-1] if authors else "paper")) or "paper"
        title_word = next((word for word in re.findall(r"[A-Za-z0-9]+", paper.title) if len(word) > 3), "work")
        base = f"{surname}{paper.year or 'nd'}{title_word}".lower()
        key = base
        index = 2
        while key in used:
            key = f"{base}{index}"
            index += 1
        used.add(key)
        return key

    def _author_names(self, authors: list[dict[str, Any]]) -> list[str]:
        names = []
        for author in authors:
            name = author.get("name") or author.get("authorName")
            if not name:
                first = author.get("first_name") or author.get("firstName") or ""
                last = author.get("last_name") or author.get("lastName") or ""
                name = f"{first} {last}".strip()
            if name:
                names.append(str(name))
        return names

    def _bib_escape(self, value: str | None) -> str:
        return (value or "").replace("{", r"\{").replace("}", r"\}").replace("\n", " ")

    def _latex_escape(self, value: str) -> str:
        replacements = {
            "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
            "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
            "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        }
        return "".join(replacements.get(char, char) for char in str(value))

    def _single_line(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _value(self, value: Any) -> str:
        return str(getattr(value, "value", value))
