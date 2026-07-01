"use client";

import Link from "next/link";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { CreateProjectForm } from "@/components/create-project-form";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import { indraApi } from "@/lib/api";
import { formatRelativeDate, truncate } from "@/lib/format";
import type { Project, ResearchSession } from "@/lib/types";

interface ProjectsData {
  projects: Project[];
  sessions: ResearchSession[];
}

export function ProjectsPageClient() {
  const [data, setData] = useState<ProjectsData>({ projects: [], sessions: [] });
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projects, sessions] = await Promise.all([
        indraApi.listProjects(),
        indraApi.listSessions(),
      ]);
      setData({ projects, sessions });
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
    setData((current) => ({ ...current, projects: [project, ...current.projects] }));
  }

  return (
    <>
      <AppHeader
        eyebrow="Workspace portfolio"
        title="Research projects"
        description="Create durable research workspaces, launch sessions, and inspect evidence without using the CLI."
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
            <span>{data.sessions.length} sessions</span>
          </div>
        </section>

        {error ? <ErrorPanel message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <p>Loading projects...</p>
        ) : filteredProjects.length === 0 ? (
          <EmptyState
            title={data.projects.length === 0 ? "No research projects yet" : "No matching projects"}
            description={
              data.projects.length === 0
                ? "Create a project to group related sessions, papers, claims, maps, advice, and exports."
                : "Change the search query to reveal other workspaces."
            }
            action={data.projects.length === 0 ? <CreateProjectForm onCreated={handleCreated} /> : undefined}
          />
        ) : (
          <div className="project-grid">
            {filteredProjects.map((project) => {
              const sessions = data.sessions.filter((session) => session.project_id === project.id);
              const active = sessions.some((session) => ["pending", "running", "paused"].includes(session.status));
              const updatedAt = sessions.reduce(
                (latest, session) =>
                  new Date(session.updated_at).getTime() > new Date(latest).getTime()
                    ? session.updated_at
                    : latest,
                project.updated_at,
              );
              return (
                <Link className="project-card" href={`/projects/${project.id}`} key={project.id}>
                  <div className="project-card-topline">
                    <span className="project-field">{project.field || "General research"}</span>
                    <StatusBadge status={active ? "active" : "idle"} compact />
                  </div>
                  <div>
                    <h2>{project.title}</h2>
                    <p>{truncate(project.description || "No project description has been added.", 150)}</p>
                  </div>
                  <dl className="metric-grid metric-grid-3">
                    <div><dt>Sessions</dt><dd>{sessions.length}</dd></div>
                    <div><dt>Status</dt><dd>{active ? "active" : "idle"}</dd></div>
                    <div><dt>Updated</dt><dd>{formatRelativeDate(updatedAt)}</dd></div>
                  </dl>
                  <div className="project-card-footer">
                    <span>Open workspace</span>
                    <span className="card-link">Open -&gt;</span>
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
