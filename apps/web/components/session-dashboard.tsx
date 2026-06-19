"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import { useSessionEventStream } from "@/hooks/use-session-event-stream";
import { erlaApi } from "@/lib/api";
import { authorNames, formatDate, truncate } from "@/lib/format";
import { buildBranchTree } from "@/lib/tree.js";
import type {
  Branch,
  Claim,
  EventRecord,
  Job,
  SessionPaperView,
  SessionSnapshot,
} from "@/lib/types";

type BranchNode = Branch & { children: BranchNode[] };
type BottomTab = "events" | "jobs" | "claims";

function mergeEvents(existing: EventRecord[], incoming: EventRecord): EventRecord[] {
  const byId = new Map(existing.map((event) => [event.id, event]));
  byId.set(incoming.id, incoming);
  return Array.from(byId.values()).sort(
    (left, right) =>
      new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
  );
}

function BranchTreeRow({
  node,
  selectedId,
  onSelect,
}: {
  node: BranchNode;
  selectedId: string | null;
  onSelect: (branch: Branch) => void;
}) {
  return (
    <li className="branch-tree-item">
      <button
        type="button"
        className={`branch-tree-row${selectedId === node.id ? " is-selected" : ""}`}
        onClick={() => onSelect(node)}
      >
        <span className="branch-tree-glyph" aria-hidden="true">
          {node.children.length > 0 ? "◇" : "·"}
        </span>
        <span className="branch-tree-copy">
          <strong>{node.label || `Branch ${node.depth + 1}`}</strong>
          <small>{truncate(node.query, 72)}</small>
        </span>
        <StatusBadge status={node.status} compact />
      </button>
      {node.children.length > 0 ? (
        <ul className="branch-tree-children">
          {node.children.map((child) => (
            <BranchTreeRow
              node={child}
              selectedId={selectedId}
              onSelect={onSelect}
              key={child.id}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function EventLog({ events }: { events: EventRecord[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No events recorded"
        description="Session lifecycle and worker events will appear here chronologically."
      />
    );
  }
  return (
    <div className="event-log">
      {[...events].reverse().map((event) => (
        <article className="event-row" key={event.id}>
          <div className={`event-severity severity-${event.severity}`} aria-hidden="true" />
          <time>{formatDate(event.created_at)}</time>
          <div>
            <strong>{event.event_type.replaceAll("_", " ")}</strong>
            <p>{Object.keys(event.payload).length ? JSON.stringify(event.payload) : "No additional payload"}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

function JobsPanel({ jobs }: { jobs: Job[] }) {
  if (jobs.length === 0) {
    return (
      <EmptyState
        title="No background jobs"
        description="Starting or continuing a session creates durable jobs for worker execution."
      />
    );
  }
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Job</th>
            <th>Status</th>
            <th>Attempts</th>
            <th>Scheduled</th>
            <th>Last error</th>
          </tr>
        </thead>
        <tbody>
          {[...jobs].reverse().map((job) => (
            <tr key={job.id}>
              <td>{job.job_type.replaceAll("_", " ")}</td>
              <td><StatusBadge status={job.status} compact /></td>
              <td>{job.attempts} / {job.max_attempts}</td>
              <td>{formatDate(job.run_at)}</td>
              <td>{job.last_error || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClaimsPanel({ claims }: { claims: Claim[] }) {
  if (claims.length === 0) {
    return (
      <EmptyState
        title="No claims extracted"
        description="Atomic claims will appear after summaries are processed by the extraction endpoint."
      />
    );
  }
  return (
    <div className="data-table-wrap">
      <table className="data-table claim-table">
        <thead>
          <tr>
            <th>Claim</th>
            <th>Type</th>
            <th>Status</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.id}>
              <td>{claim.claim_text}</td>
              <td>{claim.claim_type.replaceAll("_", " ")}</td>
              <td><StatusBadge status={claim.status} compact /></td>
              <td>{claim.confidence == null ? "—" : `${Math.round(claim.confidence * 100)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BranchInspector({
  branch,
  papers,
  busy,
  onContinue,
  onPrune,
}: {
  branch: Branch;
  papers: SessionPaperView[];
  busy: boolean;
  onContinue: () => void;
  onPrune: () => void;
}) {
  return (
    <div className="inspector-content">
      <div className="inspector-title-row">
        <div>
          <p className="eyebrow">Branch inspector</p>
          <h2>{branch.label || "Untitled branch"}</h2>
        </div>
        <StatusBadge status={branch.status} />
      </div>
      <p className="inspector-lead">{branch.query}</p>
      <dl className="metric-grid metric-grid-2 compact-metrics">
        <div><dt>Mode</dt><dd>{branch.mode.replaceAll("_", " ")}</dd></div>
        <div><dt>Depth</dt><dd>{branch.depth}</dd></div>
        <div><dt>Papers</dt><dd>{papers.length}</dd></div>
        <div><dt>Context</dt><dd>{branch.context_tokens_used.toLocaleString()} tokens</dd></div>
      </dl>
      <section className="inspector-section">
        <h3>Rationale</h3>
        <p>{branch.rationale || "No branch rationale has been persisted yet."}</p>
      </section>
      {branch.failure_reason || branch.prune_reason ? (
        <section className="inspector-section warning-section">
          <h3>{branch.failure_reason ? "Failure" : "Prune reason"}</h3>
          <p>{branch.failure_reason || branch.prune_reason}</p>
        </section>
      ) : null}
      <section className="inspector-section">
        <h3>Branch actions</h3>
        <div className="button-row">
          <button
            className="button button-primary button-small"
            type="button"
            onClick={onContinue}
            disabled={busy || branch.status === "pruned" || branch.status === "failed"}
          >
            Continue branch
          </button>
          <button
            className="button button-danger button-small"
            type="button"
            onClick={onPrune}
            disabled={busy || branch.parent_branch_id == null || branch.status === "pruned"}
          >
            Prune
          </button>
        </div>
      </section>
    </div>
  );
}

function PaperInspector({ entry }: { entry: SessionPaperView }) {
  const paper = entry.paper;
  return (
    <div className="inspector-content">
      <div className="inspector-title-row">
        <div>
          <p className="eyebrow">Paper inspector</p>
          <h2>{paper.title}</h2>
        </div>
        {entry.selected ? <StatusBadge status="selected" /> : <StatusBadge status="candidate" />}
      </div>
      <p className="paper-authors">{authorNames(paper.authors)}</p>
      <dl className="metric-grid metric-grid-2 compact-metrics">
        <div><dt>Year</dt><dd>{paper.year || "Unknown"}</dd></div>
        <div><dt>Citations</dt><dd>{paper.citation_count ?? "Unknown"}</dd></div>
        <div><dt>Venue</dt><dd>{paper.venue || "Unknown"}</dd></div>
        <div><dt>Discovery</dt><dd>{entry.discovery_method?.replaceAll("_", " ") || "Unknown"}</dd></div>
      </dl>
      <section className="inspector-section">
        <h3>Abstract</h3>
        <p>{paper.abstract || "No abstract was persisted for this paper."}</p>
      </section>
      <section className="inspector-section">
        <h3>Selection rationale</h3>
        <p>{entry.selection_reason || "No selection rationale was persisted."}</p>
      </section>
      <div className="button-row">
        <Link className="button button-primary button-small" href={`/papers/${paper.id}`}>
          Open paper page
        </Link>
        {paper.url ? (
          <a className="button button-secondary button-small" href={paper.url} target="_blank" rel="noreferrer">
            External source
          </a>
        ) : null}
      </div>
    </div>
  );
}

export function SessionDashboard({ sessionId }: { sessionId: string }) {
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [bottomTab, setBottomTab] = useState<BottomTab>("events");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const next = await erlaApi.getSessionSnapshot(sessionId);
      setSnapshot(next);
      setSelectedBranchId((current) => {
        if (current && next.branches.some((branch) => branch.id === current)) return current;
        return next.runtime_loop?.root_branch_id ?? next.branches[0]?.id ?? null;
      });
      setSelectedPaperId((current) =>
        current && next.papers.some((paper) => paper.paper_id === current) ? current : null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Session could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load(true);
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [load]);

  const handleStreamEvent = useCallback((event: EventRecord) => {
    setSnapshot((current) =>
      current ? { ...current, events: mergeEvents(current.events, event) } : current,
    );
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => void load(false), 250);
  }, [load]);

  const stream = useSessionEventStream(sessionId, handleStreamEvent);

  const branchTree = useMemo(
    () => (snapshot ? (buildBranchTree(snapshot.branches) as BranchNode[]) : []),
    [snapshot],
  );
  const selectedBranch = snapshot?.branches.find((branch) => branch.id === selectedBranchId) ?? null;
  const selectedPaper = snapshot?.papers.find((entry) => entry.paper_id === selectedPaperId) ?? null;
  const branchPapers = selectedBranch
    ? snapshot?.papers.filter((paper) => paper.branch_id === selectedBranch.id) ?? []
    : [];

  async function runAction(action: "start" | "pause" | "resume" | "cancel") {
    setBusy(true);
    setError(null);
    try {
      await erlaApi.runSessionAction(sessionId, action);
      await load(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Unable to ${action} session`);
    } finally {
      setBusy(false);
    }
  }

  async function runBranchAction(action: "continue" | "prune") {
    if (!selectedBranch) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "continue") await erlaApi.continueBranch(selectedBranch.id);
      else await erlaApi.pruneBranch(selectedBranch.id);
      await load(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Unable to ${action} branch`);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <div className="dashboard-loading">Loading durable session state…</div>;
  }

  if (error && !snapshot) {
    return (
      <main className="page-shell">
        <ErrorPanel message={error} onRetry={() => void load(true)} />
      </main>
    );
  }

  if (!snapshot) return null;
  const session = snapshot.session;

  return (
    <main className="session-dashboard">
      <header className="session-topbar">
        <div className="session-identity">
          <Link href={session.project_id ? `/projects/${session.project_id}` : "/projects"}>
            ← Workspace
          </Link>
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
          {session.status === "pending" ? (
            <button className="button button-primary button-small" type="button" onClick={() => void runAction("start")} disabled={busy}>Start</button>
          ) : null}
          {session.status === "running" ? (
            <button className="button button-secondary button-small" type="button" onClick={() => void runAction("pause")} disabled={busy}>Pause</button>
          ) : null}
          {session.status === "paused" ? (
            <button className="button button-primary button-small" type="button" onClick={() => void runAction("resume")} disabled={busy}>Resume</button>
          ) : null}
          {["pending", "running", "paused"].includes(session.status) ? (
            <button className="button button-danger button-small" type="button" onClick={() => void runAction("cancel")} disabled={busy}>Cancel</button>
          ) : null}
        </div>
      </header>

      {error ? <div className="dashboard-error"><ErrorPanel message={error} /></div> : null}

      <div className="dashboard-grid">
        <aside className="dashboard-sidebar">
          <section className="sidebar-section">
            <div className="sidebar-heading">
              <h2>Branches</h2>
              <span>{snapshot.branches.length}</span>
            </div>
            {branchTree.length === 0 ? (
              <p className="muted-copy">No branch state is available.</p>
            ) : (
              <ul className="branch-tree">
                {branchTree.map((node) => (
                  <BranchTreeRow
                    node={node}
                    selectedId={selectedBranchId}
                    onSelect={(branch) => {
                      setSelectedBranchId(branch.id);
                      setSelectedPaperId(null);
                    }}
                    key={node.id}
                  />
                ))}
              </ul>
            )}
          </section>
          <section className="sidebar-section">
            <h2>Providers</h2>
            <div className="tag-list">
              {session.source_providers.map((provider) => (
                <span className="tag" key={provider}>{provider.replaceAll("_", " ")}</span>
              ))}
            </div>
          </section>
          <section className="sidebar-section session-metadata">
            <h2>Session state</h2>
            <dl>
              <div><dt>Created</dt><dd>{formatDate(session.created_at)}</dd></div>
              <div><dt>Updated</dt><dd>{formatDate(session.updated_at)}</dd></div>
              <div><dt>Loop</dt><dd>{snapshot.runtime_loop?.loop_number ?? "—"}</dd></div>
              <div><dt>Stream</dt><dd className={stream.connected ? "text-success" : "text-muted"}>{stream.connected ? "Connected" : "Disconnected"}</dd></div>
            </dl>
            {stream.error ? <p className="stream-warning">{stream.error}</p> : null}
          </section>
        </aside>

        <section className="dashboard-center">
          <div className="center-header">
            <div>
              <p className="eyebrow">Session evidence</p>
              <h2>Papers</h2>
            </div>
            <span>{snapshot.papers.length} attached</span>
          </div>
          {snapshot.papers.length === 0 ? (
            <EmptyState
              title="No papers in this session"
              description="The dashboard is connected to durable state. Search results will appear when a worker persists papers for this run."
            />
          ) : (
            <div className="dashboard-paper-list">
              {snapshot.papers.map((entry) => (
                <button
                  className={`dashboard-paper-row${selectedPaperId === entry.paper_id ? " is-selected" : ""}`}
                  type="button"
                  key={entry.id}
                  onClick={() => {
                    setSelectedPaperId(entry.paper_id);
                    setSelectedBranchId(null);
                  }}
                >
                  <div className="paper-rank" aria-hidden="true">{entry.paper.year || "—"}</div>
                  <div>
                    <h3>{entry.paper.title}</h3>
                    <p>{authorNames(entry.paper.authors)}</p>
                    <small>{truncate(entry.paper.abstract || entry.selection_reason || "No abstract available.", 190)}</small>
                  </div>
                  <div className="paper-row-aside">
                    <span>{entry.paper.citation_count ?? 0} citations</span>
                    <StatusBadge status={entry.selected ? "selected" : "candidate"} compact />
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <aside className="dashboard-inspector">
          {selectedPaper ? (
            <PaperInspector entry={selectedPaper} />
          ) : selectedBranch ? (
            <BranchInspector
              branch={selectedBranch}
              papers={branchPapers}
              busy={busy}
              onContinue={() => void runBranchAction("continue")}
              onPrune={() => void runBranchAction("prune")}
            />
          ) : (
            <EmptyState
              title="Select a branch or paper"
              description="The inspector exposes rationale, evidence context, state, and control actions."
            />
          )}
        </aside>
      </div>

      <section className="dashboard-drawer">
        <div className="drawer-tabs" role="tablist" aria-label="Session details">
          {(["events", "jobs", "claims"] as BottomTab[]).map((tab) => (
            <button
              type="button"
              role="tab"
              aria-selected={bottomTab === tab}
              className={bottomTab === tab ? "is-active" : ""}
              onClick={() => setBottomTab(tab)}
              key={tab}
            >
              {tab}
              <span>
                {tab === "events"
                  ? snapshot.events.length
                  : tab === "jobs"
                    ? snapshot.jobs.length
                    : snapshot.claims.length}
              </span>
            </button>
          ))}
        </div>
        <div className="drawer-content">
          {bottomTab === "events" ? <EventLog events={snapshot.events} /> : null}
          {bottomTab === "jobs" ? <JobsPanel jobs={snapshot.jobs} /> : null}
          {bottomTab === "claims" ? <ClaimsPanel claims={snapshot.claims} /> : null}
        </div>
      </section>
    </main>
  );
}
