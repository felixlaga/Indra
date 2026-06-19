"use client";

import Link from "next/link";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { CreateProjectForm } from "@/components/create-project-form";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import { erlaApi } from "@/lib/api";
import { formatRelativeDate, truncate } from "@/lib/format";
import type {
  Project,
  ProjectMetrics,
  SessionSnapshot,
} from "@/lib/types";

interface DashboardData {
  projects: Project[];
  metrics: Record<string, ProjectMetrics>;
}

async function loadDashboardData(): Promise<DashboardData> {
  const [projects, sessions] = await Promise.all([
    erlaApi.listProjects(),
    erlaApi.listSessions(),
  ]);
  const snapshots = await Promise.allSettled(
    sessions.map((session) => erlaApi.getSessionSnapshot(session.id)),
  );
  const snapshotBySession = new Map<string, SessionSnapshot>();
  snapshots.forEach((result, index) => {
    if (result.status === "fulfilled") {
      snapshotBySession.set(sessions[index].id, result.value);
    }
  });

  const metrics = Object.fromEntries(
    projects.map((project) => {
      const projectSessions = sessions.filter((session) => session.project_id === project.id);
      const projectSnapshots = projectSessions
        .map((session) => snapshotBySession.get(session.id))
        .filter((snapshot): snapshot is SessionSnapshot => Boolean(snapshot));
      const uniquePaperIds = new Set(
        projectSnapshots.flatMap((snapshot) => snapshot.papers.map((paper) => paper.paper_id)),
      );
      const updatedAt = projectSessions.reduce(
        (latest, session) =>
          new Date(session.updated_at).getTime() > new Date(latest).getTime()
            ? session.updated_at
            : latest,
        project.updated_at,
      );
      return [
        project.id,
        {
          sessionCount: projectSessions.length,
          paperCount: uniquePaperIds.size,
          claimCount: projectSnapshots.reduce(
            (total, snapshot) => total + snapshot.claims.length,
            0,
          ),
          activeSessionCount: projectSessions.filter((session) =>
            ["pending", "running", "paused"].includes(session.status),
          ).length,
          updatedAt,
        } satisfies ProjectMetrics,
      ];
    }),
  );
  return { projects, metrics };
}

export function ProjectsPageClient() {
  const [data, setData] = useState<DashboardData>({ projects: [], metrics: {} });
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loadDashboardData());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Projects could not be loaded");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredProjects = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return data.projects;
    return data.projects.filter((project) =>
      [project.title, project.description, project.field]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [data.projects, search]);

  function handleCreated(project: Project) {
    setData((current) => ({
      projects: [project, ...current.projects],
      metrics: {
        ...current.metrics,
        [project.id]: {
          sessionCount: 0,
          paperCount: 0,
          claimCount: 0,
          activeSessionCount: 0,
          updatedAt: project.updated_at,
        },
      },
    }));
  }

  return (
    <>
      <AppHeader
        eyebrow="Workspace portfolio"
        title="Research projects"
        description="Create durable research workspaces, launch sessions, and inspect the evidence trail without using the CLI."
        actions={<CreateProjectForm onCreated={handleCreated} />}
      />
      <main className="page-shell">
        <section className="toolbar-row" aria-label="Project filters">
          <label className="search-field">
            <span className="sr-only">Search projects</span>
            <input
              type="search"
              value={search}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSearch(event.target.value)}
              placeholder="Search projects, fields, or descriptions"
            />
          </label>
          <div className="toolbar-meta">
            <span>{data.projects.length} projects</span>
            <span>{Object.values(data.metrics).reduce((sum, item) => sum + item.sessionCount, 0)} sessions</span>
          </div>
        </section>

        {error ? <ErrorPanel message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <div className="project-grid" aria-label="Loading projects">
            {[0, 1, 2].map((item) => (
              <div className="project-card skeleton-card" key={item} />
            ))}
          </div>
        ) : filteredProjects.length === 0 ? (
          <EmptyState
            title={data.projects.length === 0 ? "No research projects yet" : "No matching projects"}
            description={
              data.projects.length === 0
                ? "Create a project to group related research sessions, papers, claims, and future exports."
                : "Change the search query to reveal other workspaces."
            }
            action={data.projects.length === 0 ? <CreateProjectForm onCreated={handleCreated} /> : undefined}
          />
        ) : (
          <div className="project-grid">
            {filteredProjects.map((project) => {
              const metrics = data.metrics[project.id];
              return (
                <Link className="project-card" href={`/projects/${project.id}`} key={project.id}>
                  <div className="project-card-topline">
                    <span className="project-field">{project.field || "General research"}</span>
                    {metrics?.activeSessionCount ? (
                      <StatusBadge status="active" compact />
                    ) : (
                      <StatusBadge status="idle" compact />
                    )}
                  </div>
                  <div>
                    <h2>{project.title}</h2>
                    <p>{truncate(project.description || "No project description has been added.", 150)}</p>
                  </div>
                  <dl className="metric-grid metric-grid-3">
                    <div>
                      <dt>Sessions</dt>
                      <dd>{metrics?.sessionCount ?? 0}</dd>
                    </div>
                    <div>
                      <dt>Papers</dt>
                      <dd>{metrics?.paperCount ?? 0}</dd>
                    </div>
                    <div>
                      <dt>Claims</dt>
                      <dd>{metrics?.claimCount ?? 0}</dd>
                    </div>
                  </dl>
                  <div className="project-card-footer">
                    <span>Updated {formatRelativeDate(metrics?.updatedAt ?? project.updated_at)}</span>
                    <span className="card-link">Open workspace →</span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}
