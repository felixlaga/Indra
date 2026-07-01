"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { SessionCreateForm } from "@/components/session-create-form";
import { StatusBadge } from "@/components/status-badge";
import { indraApi } from "@/lib/api";
import { formatRelativeDate } from "@/lib/format";
import type { Project, ResearchSession } from "@/lib/types";

interface ProjectPageData {
  project: Project;
  sessions: ResearchSession[];
}

export function ProjectPageClient({ projectId }: { projectId: string }) {
  const [data, setData] = useState<ProjectPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [project, allSessions] = await Promise.all([
        indraApi.getProject(projectId),
        indraApi.listSessions(),
      ]);
      const sessions = allSessions
        .filter((session) => session.project_id === projectId)
        .sort(
          (left, right) =>
            new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
        );
      setData({ project, sessions });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Project could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <main className="page-shell"><p>Loading project...</p></main>;
  }
  if (error || !data) {
    return <main className="page-shell"><ErrorPanel message={error || "Project could not be loaded"} onRetry={() => void load()} /></main>;
  }

  return (
    <>
      <AppHeader
        eyebrow="Research workspace"
        title={data.project.title}
        description={data.project.description || "Create sessions and inspect the evidence trail for this workspace."}
        actions={<SessionCreateForm projectId={projectId} />}
      />
      <main className="page-shell">
        {data.sessions.length === 0 ? (
          <EmptyState
            title="No sessions yet"
            description="Create a session to start collecting branches, papers, claims, maps, advice, and exports."
            action={<SessionCreateForm projectId={projectId} />}
          />
        ) : (
          <div className="project-grid">
            {data.sessions.map((session) => (
              <Link className="project-card" href={`/sessions/${session.id}`} key={session.id}>
                <div className="project-card-topline">
                  <span className="project-field">{session.source_providers.join(", ")}</span>
                  <StatusBadge status={session.status} compact />
                </div>
                <div>
                  <h2>{session.initial_query}</h2>
                  <p>Updated {formatRelativeDate(session.updated_at)}</p>
                </div>
                <div className="project-card-footer">
                  <span>Created {formatRelativeDate(session.created_at)}</span>
                  <span className="card-link">Open session -&gt;</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
