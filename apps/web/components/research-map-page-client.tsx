"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { indraApi } from "@/lib/api";
import type { ResearchMap } from "@/lib/types";

export function ResearchMapPageClient({ sessionId }: { sessionId: string }) {
  const [researchMap, setResearchMap] = useState<ResearchMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResearchMap(await indraApi.getResearchMap(sessionId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Research map could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <main className="page-shell"><p>Loading research map...</p></main>;
  }
  if (!researchMap) {
    return <main className="page-shell"><ErrorPanel message={error || "Research map could not be loaded"} onRetry={() => void load()} /></main>;
  }

  return (
    <>
      <AppHeader
        eyebrow="Research map"
        title="Literature landscape"
        description={researchMap.overview.text}
        actions={<Link className="button button-secondary" href={`/sessions/${sessionId}`}>Back to session</Link>}
      />
      <main className="page-shell">
        {researchMap.nodes.length === 0 ? (
          <EmptyState title="No papers mapped" description="Persist papers into the session before opening the map." />
        ) : (
          <div className="project-grid">
            {researchMap.nodes.map((node) => (
              <Link className="project-card" href={`/papers/${node.paper_id}`} key={node.paper_id}>
                <div className="project-card-topline">
                  <span className="project-field">{node.year || "Unknown year"}</span>
                  <span>{node.role.replaceAll("_", " ")}</span>
                </div>
                <div>
                  <h2>{node.title}</h2>
                  <p>{node.venue || "Unknown venue"}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
