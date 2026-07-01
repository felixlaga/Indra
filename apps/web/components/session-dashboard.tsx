"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import { useSessionEventStream } from "@/hooks/use-session-event-stream";
import { indraApi } from "@/lib/api";
import { authorNames, formatDate, truncate } from "@/lib/format";
import type { EventRecord, SessionSnapshot } from "@/lib/types";

function mergeEvents(events: EventRecord[], incoming: EventRecord): EventRecord[] {
  const byId = new Map(events.map((event) => [event.id, event]));
  byId.set(incoming.id, incoming);
  return Array.from(byId.values()).sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
  );
}

export function SessionDashboard({ sessionId }: { sessionId: string }) {
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSnapshot(await indraApi.getSessionSnapshot(sessionId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Session could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const stream = useSessionEventStream(
    sessionId,
    useCallback((event: EventRecord) => {
      setSnapshot((current) =>
        current ? { ...current, events: mergeEvents(current.events, event) } : current,
      );
    }, []),
  );

  async function runSessionAction(action: "start" | "pause" | "resume" | "cancel") {
    setBusy(true);
    setError(null);
    try {
      await indraApi.runSessionAction(sessionId, action);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Unable to ${action} session`);
    } finally {
      setBusy(false);
    }
  }

  async function continueBranch(branchId: string) {
    setBusy(true);
    setError(null);
    try {
      await indraApi.continueBranch(branchId);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to continue branch");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <main className="page-shell"><p>Loading durable session state...</p></main>;
  }
  if (!snapshot) {
    return <main className="page-shell"><ErrorPanel message={error || "Session could not be loaded"} onRetry={() => void load()} /></main>;
  }

  const { session } = snapshot;
  const rootBranchId = snapshot.runtime_loop?.root_branch_id;

  return (
    <main className="session-dashboard">
      <header className="session-topbar">
        <div className="session-identity">
          <Link href={session.project_id ? `/projects/${session.project_id}` : "/projects"}>Workspace</Link>
          <div>
            <p className="eyebrow">Research session</p>
            <h1>{session.initial_query}</h1>
          </div>
        </div>
        <div className="session-summary-metrics">
          <span><strong>{snapshot.branches.length}</strong> branches</span>
          <span><strong>{snapshot.papers.length}</strong> papers</span>
          <span><strong>{snapshot.claims.length}</strong> claims</span>
        </div>
        <div className="run-controls">
          <StatusBadge status={session.status} />
          {session.status === "pending" ? <button className="button button-primary button-small" type="button" disabled={busy} onClick={() => void runSessionAction("start")}>Start</button> : null}
          {session.status === "running" ? <button className="button button-secondary button-small" type="button" disabled={busy} onClick={() => void runSessionAction("pause")}>Pause</button> : null}
          {session.status === "paused" ? <button className="button button-primary button-small" type="button" disabled={busy} onClick={() => void runSessionAction("resume")}>Resume</button> : null}
          {["pending", "running", "paused"].includes(session.status) ? <button className="button button-danger button-small" type="button" disabled={busy} onClick={() => void runSessionAction("cancel")}>Cancel</button> : null}
        </div>
      </header>

      {error ? <div className="dashboard-error"><ErrorPanel message={error} onRetry={() => void load()} /></div> : null}

      <section className="dashboard-drawer">
        <div className="drawer-tabs" role="tablist" aria-label="Session shortcuts">
          <Link className="button button-secondary button-small" href={`/sessions/${sessionId}/map`}>Research map</Link>
          <Link className="button button-secondary button-small" href={`/sessions/${sessionId}/advisor`}>Advisor</Link>
          <Link className="button button-secondary button-small" href={`/sessions/${sessionId}/exports`}>Exports</Link>
        </div>
        <p className={stream.connected ? "text-success" : "text-muted"}>Event stream: {stream.connected ? "connected" : "disconnected"}</p>
        {stream.error ? <p className="stream-warning">{stream.error}</p> : null}
      </section>

      <div className="dashboard-grid">
        <aside className="dashboard-sidebar">
          <section className="sidebar-section">
            <h2>Branches</h2>
            {snapshot.branches.length === 0 ? <p className="muted-copy">No branches persisted.</p> : (
              <div className="tag-list">
                {snapshot.branches.map((branch) => (
                  <button className="tag" type="button" key={branch.id} disabled={busy} onClick={() => void continueBranch(branch.id)}>
                    {branch.label || branch.query} - {branch.status}
                  </button>
                ))}
              </div>
            )}
          </section>
          <section className="sidebar-section session-metadata">
            <h2>Session state</h2>
            <dl>
              <div><dt>Created</dt><dd>{formatDate(session.created_at)}</dd></div>
              <div><dt>Updated</dt><dd>{formatDate(session.updated_at)}</dd></div>
              <div><dt>Root branch</dt><dd>{rootBranchId || "not persisted"}</dd></div>
            </dl>
          </section>
        </aside>

        <section className="dashboard-center">
          <div className="center-header"><h2>Papers</h2><span>{snapshot.papers.length} attached</span></div>
          {snapshot.papers.length === 0 ? (
            <EmptyState title="No papers in this session" description="Persisted search results will appear here once the worker records papers." />
          ) : (
            <div className="dashboard-paper-list">
              {snapshot.papers.map((entry) => (
                <Link className="dashboard-paper-row" href={`/papers/${entry.paper.id}`} key={entry.id}>
                  <div className="paper-rank" aria-hidden="true">{entry.paper.year || "--"}</div>
                  <div>
                    <h3>{entry.paper.title}</h3>
                    <p>{authorNames(entry.paper.authors)}</p>
                    <small>{truncate(entry.paper.abstract || entry.selection_reason || "No abstract available.", 190)}</small>
                  </div>
                  <div className="paper-row-aside"><span>{entry.paper.citation_count ?? 0} citations</span></div>
                </Link>
              ))}
            </div>
          )}
        </section>

        <aside className="dashboard-inspector">
          <section className="inspector-content">
            <h2>Claims</h2>
            {snapshot.claims.length === 0 ? <p>No claims extracted.</p> : snapshot.claims.slice(0, 8).map((claim) => (
              <Link className="claim-ledger-link" href={`/claims/${claim.id}`} key={claim.id}>
                {claim.claim_text}<span>{claim.status}</span>
              </Link>
            ))}
          </section>
        </aside>
      </div>
    </main>
  );
}
