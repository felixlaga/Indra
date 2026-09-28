"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import { HubTabs } from "@/components/session-hub/tabs";
import { ClaimLedger } from "@/components/session-hub/ledger";
import { CitationGraph } from "@/components/session-hub/graph";
import {
  ClaimMapView,
  PapersView,
  ScoutView,
  TimelineView,
} from "@/components/session-hub/views";
import { HubInspector } from "@/components/session-hub/inspector";
import { useSessionEventStream } from "@/hooks/use-session-event-stream";
import { indraApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { uniquePapers, validationSummary } from "@/lib/session-hub.js";
import type { EventRecord, ResearchMap, SessionSnapshot } from "@/lib/types";
import type { ResearchAdvice } from "@/lib/advice-types";

const views = [
  { id: "scout", label: "Scout Tree" },
  { id: "graph", label: "Citation Graph" },
  { id: "timeline", label: "Timeline" },
  { id: "claims", label: "Claim Map" },
  { id: "papers", label: "Papers" },
];
const drawers = [
  { id: "ledger", label: "Claim ledger" },
  { id: "events", label: "Events" },
  { id: "validations", label: "Validation trace" },
  { id: "jobs", label: "Jobs" },
];
function eventText(event: EventRecord) {
  for (const key of ["message", "title", "error"])
    if (typeof event.payload[key] === "string")
      return event.payload[key] as string;
  if (typeof event.payload.notes === "string")
    return validationSummary(event.payload.notes);
  return event.payload.status
    ? `Status: ${String(event.payload.status).replaceAll("_", " ")}`
    : "Recorded in session history";
}

export function SessionDashboard({ sessionId }: { sessionId: string }) {
  const params = useSearchParams();
  const view = views.some((item) => item.id === params.get("view"))
    ? params.get("view")!
    : "scout";
  const type = ["branch", "paper", "claim", "hypothesis"].includes(
    params.get("inspect") || "",
  )
    ? params.get("inspect")
    : null;
  const selectedId = type ? params.get("id") : null;
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drawer, setDrawer] = useState("ledger");
  const [map, setMap] = useState<ResearchMap | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [advice, setAdvice] = useState<ResearchAdvice | null>(null);
  const [adviceError, setAdviceError] = useState<string | null>(null);
  const [derivedBusy, setDerivedBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [retry, setRetry] = useState(0);
  const [now, setNow] = useState(Date.now());
  const seen = useRef(new Map<string, EventRecord>());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestId = useRef(0);
  const inspectorRef = useRef<HTMLElement | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (selectedId) {
      inspectorRef.current?.focus({ preventScroll: true });
      inspectorRef.current?.scrollIntoView({ block: "nearest" });
    } else returnFocus.current?.focus({ preventScroll: true });
  }, [selectedId, type, !!snapshot]);
  const load = useCallback(async () => {
    const token = ++requestId.current;
    try {
      const next = await indraApi.getSessionSnapshot(sessionId);
      if (token !== requestId.current) return;
      for (const event of next.events) seen.current.set(event.id, event);
      next.events = [...seen.current.values()].sort((a, b) =>
        a.created_at.localeCompare(b.created_at),
      );
      setSnapshot(next);
      setError(null);
      setRevision((value) => value + 1);
    } catch (caught) {
      if (token === requestId.current)
        setError(
          caught instanceof Error ? caught.message : "Session could not load",
        );
    }
  }, [sessionId]);
  useEffect(() => {
    seen.current.clear();
    setSnapshot(null);
    setMap(null);
    setAdvice(null);
    void load();
    return () => {
      requestId.current++;
      if (timer.current) clearTimeout(timer.current);
      timer.current = null;
    };
  }, [load]);
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);
  const onEvent = useCallback(
    (event: EventRecord) => {
      if (seen.current.has(event.id)) return;
      seen.current.set(event.id, event);
      setSnapshot((current) =>
        current
          ? {
              ...current,
              events: [...current.events, event],
              jobs:
                event.event_type === "research_progress"
                  ? current.jobs.map((job) =>
                      job.id === event.payload.job_id
                        ? {
                            ...job,
                            result: { ...job.result, ...event.payload },
                          }
                        : job,
                    )
                  : current.jobs,
            }
          : current,
      );
      // Coalesce bursts without postponing refresh forever; progress is patched locally.
      if (event.event_type !== "research_progress" && !timer.current)
        timer.current = setTimeout(() => {
          timer.current = null;
          void load();
        }, 500);
    },
    [load],
  );
  const stream = useSessionEventStream(sessionId, onEvent);
  useEffect(() => {
    if (view !== "graph" && view !== "claims" && type !== "hypothesis") return;
    let active = true;
    setDerivedBusy(true);
    const requests: Promise<unknown>[] = [];
    if (view === "graph") {
      setMapError(null);
      requests.push(
        indraApi
          .getResearchMap(sessionId)
          .then((value) => {
            if (active) setMap(value);
          })
          .catch((caught) => {
            if (active)
              setMapError(
                caught instanceof Error
                  ? caught.message
                  : "Graph could not load",
              );
          }),
      );
    }
    if (view === "claims" || type === "hypothesis") {
      setAdviceError(null);
      requests.push(
        indraApi
          .getResearchAdvice(sessionId)
          .then((value) => {
            if (active) setAdvice(value);
          })
          .catch((caught) => {
            if (active)
              setAdviceError(
                caught instanceof Error
                  ? caught.message
                  : "Advisor proposals could not load",
              );
          }),
      );
    }
    void Promise.all(requests).finally(() => {
      if (active) setDerivedBusy(false);
    });
    return () => {
      active = false;
    };
  }, [sessionId, view, type, revision, retry]);
  function navigate(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === null) next.delete(key);
      else next.set(key, value);
    }
    window.history.pushState(
      null,
      "",
      `/sessions/${sessionId}?${next.toString()}`,
    );
  }
  function select(kind: string, id: string) {
    if (!selectedId)
      returnFocus.current = document.activeElement as HTMLElement;
    navigate({ inspect: kind, id });
  }
  async function runAction(action: "start" | "pause" | "resume" | "cancel") {
    setBusy(true);
    setError(null);
    try {
      await indraApi.runSessionAction(sessionId, action);
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Session action failed",
      );
    } finally {
      setBusy(false);
    }
  }
  async function branchAction(id: string, action: "continue" | "prune") {
    setBusy(true);
    try {
      if (action === "continue") await indraApi.continueBranch(id);
      else await indraApi.pruneBranch(id);
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Branch action failed",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!snapshot)
    return (
      <main className="page-shell">
        {error ? (
          <ErrorPanel message={error} onRetry={() => void load()} />
        ) : (
          <p role="status">Loading session…</p>
        )}
      </main>
    );
  const session = snapshot.session;
  const activeJob = [...snapshot.jobs]
    .reverse()
    .find((job) => ["running", "queued"].includes(job.status));
  const lastJob = activeJob ?? snapshot.jobs.at(-1);
  const progress =
    typeof lastJob?.result.message === "string" ? lastJob.result.message : null;
  const elapsed = session.started_at
    ? Math.max(
        0,
        Math.floor(
          ((session.completed_at
            ? Date.parse(session.completed_at)
            : session.status === "running"
              ? now
              : Date.parse(session.updated_at)) -
            Date.parse(session.started_at)) /
            1000,
        ),
      )
    : 0;
  const validationCount = new Set(
    snapshot.events
      .filter((event) => event.event_type === "claim_validated")
      .map((event) => event.payload.claim_id),
  ).size;
  return (
    <main className="session-hub">
      <header className="hub-header">
        <div>
          <Link
            className="hub-back"
            href={
              session.project_id
                ? `/projects/${session.project_id}`
                : "/projects"
            }
          >
            ← Workspace
          </Link>
          <p className="eyebrow">Research session</p>
          <h1>{session.initial_query}</h1>
        </div>
        <div className="hub-run-controls">
          <StatusBadge status={session.status} />
          {["pending", "failed"].includes(session.status) && (
            <button
              className="button button-primary button-small"
              disabled={busy}
              onClick={() => void runAction("start")}
            >
              {session.status === "failed" ? "Retry" : "Start"}
            </button>
          )}
          {session.status === "running" && (
            <button
              className="button button-secondary button-small"
              disabled={busy}
              onClick={() => void runAction("pause")}
            >
              Pause
            </button>
          )}
          {session.status === "paused" && (
            <button
              className="button button-primary button-small"
              disabled={busy}
              onClick={() => void runAction("resume")}
            >
              Resume
            </button>
          )}
          {["pending", "running", "paused"].includes(session.status) && (
            <button
              className="button button-danger button-small"
              disabled={busy}
              onClick={() => void runAction("cancel")}
            >
              Cancel
            </button>
          )}
          <Link
            className="button button-secondary button-small"
            href={`/sessions/${sessionId}/advisor`}
          >
            Advisor
          </Link>
          <Link
            className="button button-secondary button-small"
            href={`/sessions/${sessionId}/exports`}
          >
            Export
          </Link>
        </div>
      </header>
      <div className="hub-metrics">
        <span>{snapshot.branches.length} branches</span>
        <span>{uniquePapers(snapshot.papers).length} papers</span>
        <span>{snapshot.claims.length} claims</span>
        <span>
          {validationCount}/{snapshot.claims.length} claims checked
        </span>
        <span title="Wall time since start, including pauses">
          Elapsed {Math.floor(elapsed / 60)}m {elapsed % 60}s
        </span>
        <span className={stream.connected ? "text-success" : "hub-warning"}>
          {stream.connected
            ? "Live updates connected"
            : "Live updates reconnecting"}
        </span>
      </div>
      <div className="hub-progress" role="status" aria-live="polite">
        {activeJob?.status === "queued"
          ? "Queued — waiting for a research worker."
          : progress ||
            (session.status === "pending"
              ? "Ready to start. Research will find papers and build an evidence ledger."
              : `Session ${session.status}.`)}
        {lastJob?.result.verification_mode === "retrieval_only"
          ? " Claims need review; no verification model was configured."
          : ""}
      </div>
      {activeJob?.status === "queued" &&
        now - Date.parse(activeJob.updated_at) > 30000 && (
          <p className="hub-warning hub-note">
            No worker has picked up this job yet. Check that the research worker
            is running.
          </p>
        )}
      {stream.error && (
        <p className="hub-warning hub-note">
          {stream.error}. Showing saved results while reconnecting.
        </p>
      )}
      {error && <ErrorPanel message={error} onRetry={() => void load()} />}
      <details className="hub-run-details">
        <summary>Run details</summary>
        <dl>
          <div>
            <dt>Sources</dt>
            <dd>
              {session.source_providers
                .map((name) =>
                  name === "arxiv" ? "arXiv" : name.replaceAll("_", " "),
                )
                .join(", ")}
            </dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{formatDate(session.created_at)}</dd>
          </div>
          <div>
            <dt>Research filters</dt>
            <dd>
              {Object.keys(session.filters).length
                ? Object.entries(session.filters)
                    .map(
                      ([key, value]) =>
                        `${key.replaceAll("_", " ")}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`,
                    )
                    .join(" · ")
                : "No additional filters"}
            </dd>
          </div>
        </dl>
      </details>
      <div className={`hub-workspace${selectedId ? " has-inspector" : ""}`}>
        <section className="hub-main">
          <HubTabs
            id="research"
            label="Research views"
            tabs={views}
            value={view}
            onChange={(value) => navigate({ view: value })}
          />
          {views.map((item) => (
            <div
              key={item.id}
              role="tabpanel"
              id={`research-panel-${item.id}`}
              aria-labelledby={`research-tab-${item.id}`}
              hidden={view !== item.id}
              tabIndex={0}
            >
              {view === item.id && (
                <>
                  {view === "scout" && (
                    <ScoutView snapshot={snapshot} select={select} />
                  )}{" "}
                  {view === "papers" && (
                    <PapersView snapshot={snapshot} select={select} />
                  )}{" "}
                  {view === "timeline" && (
                    <TimelineView snapshot={snapshot} select={select} />
                  )}{" "}
                  {view === "claims" && (
                    <ClaimMapView
                      snapshot={snapshot}
                      advice={advice}
                      adviceError={adviceError}
                      loading={derivedBusy}
                      select={select}
                      retry={() => setRetry((n) => n + 1)}
                    />
                  )}
                  {view === "graph" && (
                    <>
                      {derivedBusy && (
                        <p role="status" className="hub-note">
                          Updating citation graph…
                        </p>
                      )}
                      {mapError && (
                        <ErrorPanel
                          message={mapError}
                          onRetry={() => setRetry((n) => n + 1)}
                        />
                      )}{" "}
                      {map && (
                        <CitationGraph
                          map={map}
                          snapshot={snapshot}
                          select={select}
                          selectedId={type === "paper" ? selectedId : null}
                        />
                      )}
                    </>
                  )}
                </>
              )}
            </div>
          ))}
        </section>
        <aside
          ref={inspectorRef}
          tabIndex={-1}
          className={`hub-inspector${selectedId ? " is-open" : ""}`}
          aria-label="Research inspector"
          onKeyDown={(event) => {
            if (event.key === "Escape") navigate({ inspect: null, id: null });
          }}
        >
          <HubInspector
            key={`${type}:${selectedId}`}
            snapshot={snapshot}
            type={type}
            id={selectedId}
            select={select}
            close={() => navigate({ inspect: null, id: null })}
            advice={advice}
            busy={busy}
            branchAction={(id, action) => void branchAction(id, action)}
            refresh={() => void load()}
          />
          {type === "hypothesis" && adviceError && (
            <ErrorPanel
              message={adviceError}
              onRetry={() => setRetry((n) => n + 1)}
            />
          )}
        </aside>
      </div>
      <section className="hub-drawer">
        <HubTabs
          id="details"
          label="Session details"
          tabs={drawers}
          value={drawer}
          onChange={setDrawer}
        />
        {drawers.map((item) => (
          <div
            key={item.id}
            role="tabpanel"
            id={`details-panel-${item.id}`}
            aria-labelledby={`details-tab-${item.id}`}
            hidden={drawer !== item.id}
            tabIndex={0}
          >
            {item.id === "ledger" && (
              <ClaimLedger
                snapshot={snapshot}
                select={select}
                selectedId={type === "claim" ? selectedId : null}
              />
            )}
            {drawer === item.id &&
              ["events", "validations"].includes(item.id) && (
                <div className="hub-events">
                  {[...snapshot.events]
                    .reverse()
                    .filter(
                      (event) =>
                        item.id === "events" ||
                        event.event_type === "claim_validated",
                    )
                    .map((event) => (
                      <article key={event.id}>
                        <time>{formatDate(event.created_at)}</time>
                        <div>
                          <strong>
                            {event.event_type.replaceAll("_", " ")}
                          </strong>
                          <p>{eventText(event)}</p>
                          {typeof event.payload.claim_id === "string" && (
                            <button
                              className="hub-text-button"
                              onClick={() =>
                                select(
                                  "claim",
                                  event.payload.claim_id as string,
                                )
                              }
                            >
                              Inspect claim
                            </button>
                          )}
                        </div>
                      </article>
                    ))}
                  {item.id === "validations" &&
                    !snapshot.events.some(
                      (event) => event.event_type === "claim_validated",
                    ) && (
                      <p className="hub-note">
                        No validation checks recorded yet.
                      </p>
                    )}
                </div>
              )}
            {drawer === item.id && item.id === "jobs" && (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      {[
                        "Job",
                        "Status",
                        "Attempts",
                        "Scheduled",
                        "Last error",
                      ].map((label) => (
                        <th key={label} scope="col">
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {snapshot.jobs.map((job) => (
                      <tr key={job.id}>
                        <td>{job.job_type.replaceAll("_", " ")}</td>
                        <td>
                          <StatusBadge status={job.status} />
                        </td>
                        <td>
                          {job.attempts}/{job.max_attempts}
                        </td>
                        <td>{formatDate(job.run_at)}</td>
                        <td>{job.last_error || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!snapshot.jobs.length && (
                  <p className="hub-note">
                    No jobs yet. Start the session to begin research.
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </section>
    </main>
  );
}
