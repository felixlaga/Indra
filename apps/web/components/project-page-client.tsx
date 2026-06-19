"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { SessionCreateForm } from "@/components/session-create-form";
import { StatusBadge } from "@/components/status-badge";
import { erlaApi } from "@/lib/api";
import { authorNames, formatDate, formatRelativeDate, truncate } from "@/lib/format";
import type {
  Project,
  ResearchSession,
  SessionPaperView,
  SessionSnapshot,
} from "@/lib/types";

interface ProjectPageData {
  project: Project;
  sessions: ResearchSession[];
  snapshots: SessionSnapshot[];
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
        erlaApi.getProject(projectId),
        erlaApi.listSessions(),
      ]);
      const sessions = allSessions
        .filter((session) => session.project_id === projectId)
        .sort(
          (left, right) =>
            new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
        );
      const snapshotResults = await Promise.allSettled(
        sessions.map((session) => erlaApi.getSessionSnapshot(session.id)),
      );
      const snapshots = snapshotResults
        .filter(
          (result): result is PromiseFulfilledResult<SessionSnapshot> =>
            result.status === "fulfilled",
        )
        .map((result) => result.value);
      setData({ project, sessions, snapshots });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Project could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const papers = useMemo(() => {
    if (!data) return [];
    const byId = new Map<string, SessionPaperView>();
    for (const snapshot of data.snapshots) {
      for (const paper of snapshot.papers) byId.set(paper.paper_id, paper);
    }
    return Array.from(byId.values()).sort(
      (left, right) => (right.paper.citation_count ?? 0) - (left.paper.citation_count ?? 0),
    );
  }, [data]);

  if (loading) {
    return (
      <>
        <AppHeader title="Loading project…" />
        <main className="page-shell">
          <div className="detail-skeleton" />
        </main>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <AppHeader title="Project unavailable" />
        <main className="page-shell">
          <ErrorPanel message={error ?? "The project was not found"} onRetry={() => void load()} />
        </main>
      </>
    );
  }

  const claimCount = data.snapshots.reduce(
    (total, snapshot) => total + snapshot.claims.length,
    0,
  );
  const activeSessions = data.sessions.filter((session) =>
    ["pending", "running", "paused"].includes(session.status),
  ).length;

  return (
    <>
      <AppHeader
        eyebrow={data.project.field || "Research workspace"}
        title={data.project.title}
        description={data.project.description || "No project description has been added."}
        actions={
          <Link className="button button-secondary" href="/projects">
            All projects
          </Link>
        }
      />
      <main className="page-shell project-detail-layout">
        <section className="project-overview-strip">
          <dl className="metric-grid metric-grid-4">
            <div>
              <dt>Sessions</dt>
              <dd>{data.sessions.length}</dd>
            </div>
            <div>
              <dt>Active</dt>
              <dd>{activeSessions}</dd>
            </div>
            <div>
              <dt>Saved papers</dt>
              <dd>{papers.length}</dd>
            </div>
            <div>
              <dt>Claims</dt>
              <dd>{claimCount}</dd>
            </div>
          </dl>
          <p>Workspace updated {formatRelativeDate(data.project.updated_at)}</p>
        </section>

        <SessionCreateForm projectId={projectId} />

        <section className="content-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Research history</p>
              <h2>Recent sessions</h2>
            </div>
            <span>{data.sessions.length} total</span>
          </div>
          {data.sessions.length === 0 ? (
            <EmptyState
              title="No sessions yet"
              description="Use the research-run form above to create the root branch and durable session state."
            />
          ) : (
            <div className="session-list">
              {data.sessions.map((session) => {
                const snapshot = data.snapshots.find(
                  (candidate) => candidate.session.id === session.id,
                );
                return (
                  <Link className="session-row" href={`/sessions/${session.id}`} key={session.id}>
                    <div className="session-row-main">
                      <StatusBadge status={session.status} compact />
                      <div>
                        <h3>{session.initial_query}</h3>
                        <p>
                          {session.source_providers.join(", ") || "No providers configured"}
                          {session.failure_reason ? ` · ${session.failure_reason}` : ""}
                        </p>
                      </div>
                    </div>
                    <dl className="session-row-metrics">
                      <div>
                        <dt>Branches</dt>
                        <dd>{snapshot?.branches.length ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Papers</dt>
                        <dd>{snapshot?.papers.length ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{formatRelativeDate(session.updated_at)}</dd>
                      </div>
                    </dl>
                  </Link>
                );
              })}
            </div>
          )}
        </section>

        <section className="content-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Evidence library</p>
              <h2>Saved papers</h2>
            </div>
            <span>{papers.length} unique</span>
          </div>
          {papers.length === 0 ? (
            <EmptyState
              title="No papers have been attached"
              description="Papers will appear here when worker execution persists search results to the session."
            />
          ) : (
            <div className="paper-grid">
              {papers.slice(0, 12).map((entry) => (
                <Link className="paper-card" href={`/papers/${entry.paper_id}`} key={entry.paper_id}>
                  <div className="paper-card-meta">
                    <span>{entry.paper.year || "Year unknown"}</span>
                    <span>{entry.paper.citation_count ?? 0} citations</span>
                  </div>
                  <h3>{entry.paper.title}</h3>
                  <p className="paper-authors">{authorNames(entry.paper.authors)}</p>
                  <p>{truncate(entry.paper.abstract || entry.selection_reason || "No abstract available.", 180)}</p>
                  <div className="paper-card-footer">
                    <span>{entry.paper.venue || "Venue unavailable"}</span>
                    <span>{formatDate(entry.created_at)}</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      </main>
    </>
  );
}
