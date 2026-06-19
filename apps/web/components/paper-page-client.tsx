"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { ErrorPanel } from "@/components/error-panel";
import { erlaApi } from "@/lib/api";
import { authorNames, formatDate } from "@/lib/format";
import type { Paper } from "@/lib/types";

export function PaperPageClient({ paperId }: { paperId: string }) {
  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPaper(await erlaApi.getPaper(paperId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Paper could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [paperId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <>
        <AppHeader title="Loading paper…" />
        <main className="page-shell"><div className="detail-skeleton" /></main>
      </>
    );
  }

  if (error || !paper) {
    return (
      <>
        <AppHeader title="Paper unavailable" />
        <main className="page-shell">
          <ErrorPanel message={error ?? "The paper was not found"} onRetry={() => void load()} />
        </main>
      </>
    );
  }

  return (
    <>
      <AppHeader
        eyebrow={[paper.venue, paper.year].filter(Boolean).join(" · ") || "Paper record"}
        title={paper.title}
        description={authorNames(paper.authors)}
        actions={
          <div className="button-row">
            <Link className="button button-secondary" href="/projects">Projects</Link>
            {paper.url ? (
              <a className="button button-primary" href={paper.url} target="_blank" rel="noreferrer">
                Open source
              </a>
            ) : null}
          </div>
        }
      />
      <main className="page-shell paper-detail-layout">
        <section className="paper-detail-main">
          <div className="content-section">
            <div className="section-heading"><h2>Abstract</h2></div>
            <p className="long-copy">{paper.abstract || "No abstract is available for this paper."}</p>
          </div>
          <div className="content-section">
            <div className="section-heading"><h2>Evidence status</h2></div>
            <div className="evidence-status-grid">
              <div>
                <span className="evidence-indicator" aria-hidden="true" />
                <strong>Metadata record</strong>
                <p>Durably identified by the API canonical key.</p>
              </div>
              <div>
                <span className={`evidence-indicator${paper.pdf_url || paper.open_access_pdf_url ? " is-ready" : ""}`} aria-hidden="true" />
                <strong>Full text</strong>
                <p>{paper.pdf_url || paper.open_access_pdf_url ? "A PDF location is available." : "No PDF location is stored."}</p>
              </div>
              <div>
                <span className="evidence-indicator" aria-hidden="true" />
                <strong>Claim extraction</strong>
                <p>Inspect the originating session for extracted claims and evidence.</p>
              </div>
            </div>
          </div>
        </section>
        <aside className="paper-detail-sidebar">
          <section className="content-section">
            <div className="section-heading"><h2>Metadata</h2></div>
            <dl className="metadata-list">
              <div><dt>Canonical key</dt><dd>{paper.canonical_key}</dd></div>
              <div><dt>Year</dt><dd>{paper.year || "Unknown"}</dd></div>
              <div><dt>Venue</dt><dd>{paper.venue || "Unknown"}</dd></div>
              <div><dt>Citations</dt><dd>{paper.citation_count ?? "Unknown"}</dd></div>
              <div><dt>References</dt><dd>{paper.reference_count ?? "Unknown"}</dd></div>
              <div><dt>DOI</dt><dd>{paper.doi || "—"}</dd></div>
              <div><dt>arXiv</dt><dd>{paper.arxiv_id || "—"}</dd></div>
              <div><dt>Semantic Scholar</dt><dd>{paper.semantic_scholar_id || "—"}</dd></div>
              <div><dt>Updated</dt><dd>{formatDate(paper.updated_at)}</dd></div>
            </dl>
          </section>
        </aside>
      </main>
    </>
  );
}
