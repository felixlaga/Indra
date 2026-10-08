"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { ResearchGraph } from "@/components/research-graph/research-graph";
import { indraApi } from "@/lib/api";
import type { ResearchMap } from "@/lib/types";

import styles from "./research-map-page.module.css";

function shorten(title: string, length = 34): string {
  return title.length <= length ? title : `${title.slice(0, length - 1)}…`;
}

export function ResearchMapPageClient({ sessionId }: { sessionId: string }) {
  const [researchMap, setResearchMap] = useState<ResearchMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    setError(null);
    try {
      setResearchMap(await indraApi.getResearchMap(sessionId, controller.signal));
    } catch (caught) {
      if (controller.signal.aborted) return;
      setError(caught instanceof Error ? caught.message : "Research map could not be loaded");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
    return () => pending.current?.abort();
  }, [load]);

  if (loading) {
    return (
      <>
        <AppHeader title="Loading research map…" />
        <main className="page-shell"><p role="status">Preparing the research map in the background…</p><div className="detail-skeleton" /></main>
      </>
    );
  }

  if (error && !researchMap) {
    return (
      <>
        <AppHeader title="Research map unavailable" />
        <main className="page-shell">
          <ErrorPanel message={error} onRetry={() => void indraApi.retryResearchViews(sessionId).then(load).catch((error) => setError(error.message))} />
        </main>
      </>
    );
  }

  if (!researchMap) return null;
  const nodeById = new Map(researchMap.nodes.map((node) => [node.paper_id, node]));

  return (
    <>
      <AppHeader
        eyebrow="Research landscape"
        title="Research graph, timeline, and thematic map"
        description="Papers read and papers found by the searches, with observed citation paths. Related-paper recommendations are session-local. Foundational labels are relative to this retrieved session."
        actions={
          <Link className="button button-secondary" href={`/sessions/${sessionId}`}>
            Back to session
          </Link>
        }
      />
      <main className={`page-shell ${styles.layout}`}>
        {error ? <ErrorPanel message={error} /> : null}

        <section className={styles.overview}>
          <div>
            <p className="eyebrow">Field overview</p>
            <p>{researchMap.overview.text}</p>
            <ul className={styles.caveats}>
              {researchMap.overview.caveats.map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          </div>
          <div className={styles.metrics}>
            <div className={styles.metric}><span>Papers read</span><strong>{researchMap.overview.paper_count}</strong></div>
            <div className={styles.metric}><span>Papers found</span><strong>{researchMap.overview.discovered_paper_count ?? 0}</strong></div>
            <div className={styles.metric}><span>Clusters</span><strong>{researchMap.overview.cluster_count}</strong></div>
            <div className={styles.metric}><span>Citation paths</span><strong>{researchMap.overview.observed_citation_edge_count}</strong></div>
            <div className={styles.metric}><span>Recent papers</span><strong>{researchMap.overview.recent_paper_count}</strong></div>
          </div>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <p className="eyebrow">Research graph</p>
              <h2>Session literature landscape</h2>
            </div>
            <span>{researchMap.edges.filter((edge) => edge.observed).length} citation paths</span>
          </div>
          {researchMap.nodes.length === 0 ? (
            <EmptyState
              title="No papers to map"
              description="Papers will appear here after they are persisted in the research session."
            />
          ) : (
            <ResearchGraph map={researchMap} />
          )}
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className="eyebrow">Related papers</p><h2>Recommendations</h2></div>
          </div>
          {researchMap.recommendations.slice(0, 8).map((recommendation) => {
            const source = nodeById.get(recommendation.source_paper_id);
            const target = nodeById.get(recommendation.target_paper_id);
            return (
              <div className={styles.recommendation} key={`${recommendation.source_paper_id}:${recommendation.target_paper_id}`}>
                <Link href={`/papers/${recommendation.target_paper_id}`}>
                  {source ? shorten(source.title, 25) : "Paper"} → {target ? shorten(target.title, 30) : "Related paper"}
                </Link>
                <p>{recommendation.reason} · {Math.round(recommendation.score * 100)}%</p>
              </div>
            );
          })}
          {researchMap.recommendations.length === 0 ? (
            <p className="muted-copy">No sufficiently related session-paper pairs were found.</p>
          ) : null}
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className="eyebrow">Timeline</p><h2>Publication chronology</h2></div>
            <span>{researchMap.timeline.length} represented years</span>
          </div>
          <div className={styles.timeline}>
            {researchMap.timeline.map((bucket) => (
              <div className={styles.yearBucket} key={bucket.year}>
                <strong>{bucket.year}</strong>
                <span>{bucket.paper_ids.length} paper{bucket.paper_ids.length === 1 ? "" : "s"}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className="eyebrow">Clusters</p><h2>Thematic and branch groups</h2></div>
          </div>
          <div className={styles.cardGrid}>
            {researchMap.clusters.map((cluster) => (
              <article className={styles.card} key={cluster.id}>
                <h3>{cluster.label}</h3>
                <p>{cluster.paper_ids.length} paper{cluster.paper_ids.length === 1 ? "" : "s"}</p>
                <div className={styles.tags}>
                  {cluster.keywords.map((keyword) => <span className={styles.tag} key={keyword}>{keyword}</span>)}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className="eyebrow">Branch synthesis</p><h2>What each branch currently establishes</h2></div>
          </div>
          <div className={styles.cardGrid}>
            {researchMap.branch_syntheses.map((synthesis) => (
              <article className={styles.card} key={synthesis.branch_id}>
                <h3>{synthesis.label}</h3>
                <p>{synthesis.text}</p>
                <div className={styles.tags}>
                  <span className={styles.tag}>{synthesis.source.replaceAll("_", " ")}</span>
                  {synthesis.validation_status ? <span className={styles.tag}>{synthesis.validation_status.replaceAll("_", " ")}</span> : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
