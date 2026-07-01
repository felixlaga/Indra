"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import { indraApi } from "@/lib/api";
import { edgeCoordinates, layoutResearchMap } from "@/lib/map-layout.js";
import type { ResearchMap } from "@/lib/types";

import styles from "./research-map-page.module.css";

const GRAPH_WIDTH = 1040;
const GRAPH_HEIGHT = 560;

function shorten(title: string, length = 34): string {
  return title.length <= length ? title : `${title.slice(0, length - 1)}…`;
}

export function ResearchMapPageClient({ sessionId }: { sessionId: string }) {
  const [researchMap, setResearchMap] = useState<ResearchMap | null>(null);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await indraApi.getResearchMap(sessionId);
      setResearchMap(next);
      setSelectedPaperId((current) =>
        current && next.nodes.some((node) => node.paper_id === current)
          ? current
          : next.nodes[0]?.paper_id ?? null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Research map could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const positionedNodes = useMemo(
    () =>
      researchMap
        ? layoutResearchMap(
            researchMap.nodes,
            researchMap.clusters,
            GRAPH_WIDTH,
            GRAPH_HEIGHT,
          )
        : [],
    [researchMap],
  );

  if (loading) {
    return (
      <>
        <AppHeader title="Loading research map…" />
        <main className="page-shell"><div className="detail-skeleton" /></main>
      </>
    );
  }

  if (error && !researchMap) {
    return (
      <>
        <AppHeader title="Research map unavailable" />
        <main className="page-shell">
          <ErrorPanel message={error} onRetry={() => void load()} />
        </main>
      </>
    );
  }

  if (!researchMap) return null;
  const nodeById = new Map(researchMap.nodes.map((node) => [node.paper_id, node]));
  const selectedNode = selectedPaperId ? nodeById.get(selectedPaperId) ?? null : null;

  return (
    <>
      <AppHeader
        eyebrow="Research landscape"
        title="Citation, timeline, and thematic map"
        description="Observed citation paths are separated from session-local related-paper recommendations. Foundational labels are relative to this retrieved session."
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
            <div className={styles.metric}><span>Papers</span><strong>{researchMap.overview.paper_count}</strong></div>
            <div className={styles.metric}><span>Clusters</span><strong>{researchMap.overview.cluster_count}</strong></div>
            <div className={styles.metric}><span>Citation paths</span><strong>{researchMap.overview.observed_citation_edge_count}</strong></div>
            <div className={styles.metric}><span>Recent papers</span><strong>{researchMap.overview.recent_paper_count}</strong></div>
          </div>
        </section>

        <div className={styles.mainGrid}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <div>
                <p className="eyebrow">Citation graph</p>
                <h2>Session literature landscape</h2>
              </div>
              <span>{researchMap.edges.length} visible relations</span>
            </div>
            {researchMap.nodes.length === 0 ? (
              <EmptyState
                title="No papers to map"
                description="Papers will appear here after they are persisted in the research session."
              />
            ) : (
              <>
                <div className={styles.graphWrap}>
                  <svg
                    className={styles.graph}
                    viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
                    aria-label="Research paper citation and related-paper graph"
                  >
                    <defs>
                      <marker id="citation-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                        <path d="M0,0 L8,4 L0,8 z" fill="#6aa9ff" />
                      </marker>
                    </defs>
                    {researchMap.edges.map((edge) => {
                      const coordinates = edgeCoordinates(edge, positionedNodes);
                      if (!coordinates) return null;
                      return (
                        <line
                          key={edge.id}
                          {...coordinates}
                          className={edge.observed ? styles.observedEdge : styles.relatedEdge}
                          markerEnd={edge.observed && edge.edge_type === "cites" ? "url(#citation-arrow)" : undefined}
                        >
                          <title>{edge.observed ? edge.provenance : "Inferred related-paper relation"}</title>
                        </line>
                      );
                    })}
                    {positionedNodes.map((node) => (
                      <g
                        key={node.paper_id}
                        role="button"
                        tabIndex={0}
                        aria-label={`Open ${node.title}`}
                        className={`${styles.node} ${
                          node.role === "foundational_candidate"
                            ? styles.foundational
                            : node.role === "recent"
                              ? styles.recent
                              : ""
                        } ${selectedPaperId === node.paper_id ? styles.selectedNode : ""}`}
                        transform={`translate(${node.x} ${node.y})`}
                        onClick={() => setSelectedPaperId(node.paper_id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            setSelectedPaperId(node.paper_id);
                          }
                        }}
                      >
                        <circle r={node.radius} />
                        <text x={node.radius + 6} y={4}>{shorten(node.title)}</text>
                        <title>{node.title}</title>
                      </g>
                    ))}
                  </svg>
                </div>
                <div className={styles.legend}>
                  <span><i className={styles.foundationalMark} /> Foundational candidate</span>
                  <span><i className={styles.recentMark} /> Recent in session</span>
                  <span><i /> Established / undated</span>
                  <span>Solid arrows: observed citation metadata</span>
                  <span>Dashed lines: inferred related papers</span>
                </div>
              </>
            )}
          </section>

          <aside className={styles.sidebar}>
            <section className={`${styles.panel} ${styles.paperInspector}`}>
              <div className={styles.panelHeader}>
                <div><p className="eyebrow">Paper inspector</p><h2>Selected node</h2></div>
              </div>
              {selectedNode ? (
                <>
                  <h3>{selectedNode.title}</h3>
                  <p><StatusBadge status={selectedNode.role} compact /></p>
                  <div className={styles.paperMeta}>
                    <div><span>Year</span><strong>{selectedNode.year ?? "Unknown"}</strong></div>
                    <div><span>Citations</span><strong>{selectedNode.citation_count}</strong></div>
                    <div><span>Venue</span><strong>{selectedNode.venue || "Unknown"}</strong></div>
                    <div><span>Score</span><strong>{Math.round(selectedNode.foundational_score * 100)}%</strong></div>
                  </div>
                  <p>The score is a session-relative age/citation signal, not a quality score.</p>
                  <Link className="button button-primary button-small" href={`/papers/${selectedNode.paper_id}`}>
                    Open paper
                  </Link>
                </>
              ) : (
                <EmptyState title="Select a paper" description="Choose a graph node to inspect its role and metadata." />
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
          </aside>
        </div>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>