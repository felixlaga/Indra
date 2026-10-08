"use client";
import { useState } from "react";

import { THEME_COLORS } from "@/lib/research-graph.js";
import type { Job, ResearchMap, ResearchMapNode } from "@/lib/types";

export interface Expansion {
  /** The session's latest network-expansion job, if any. */
  job: Job | null;
  onExpand: (papers: number) => Promise<void>;
}

const SIZES = [50, 100, 200];
const ACTIVE = new Set(["queued", "running", "paused"]);

/** Grow the network: follow citations from the session's papers and search deeper. */
export function ExpandControl({ expansion }: { expansion: Expansion }) {
  const [papers, setPapers] = useState(100);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const job = expansion.job;
  const active = !!job && ACTIVE.has(job.status);
  const message = typeof job?.result?.message === "string" ? job.result.message : null;
  let status: string | null = null;
  if (job && active) status = message ?? "Waiting for the research worker…";
  else if (job?.status === "succeeded") status = message;
  else if (job && job.last_error) status = `Last expansion failed: ${job.last_error}`;

  async function expand() {
    setBusy(true);
    setError(null);
    try {
      await expansion.onExpand(papers);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Expansion could not start");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rg-expand">
      <label>
        Grow by{" "}
        <select value={papers} onChange={(event) => setPapers(Number(event.target.value))} disabled={active}>
          {SIZES.map((size) => (
            <option key={size} value={size}>
              {size} papers
            </option>
          ))}
        </select>
      </label>
      <button className="button button-small button-primary" onClick={() => void expand()} disabled={busy || active}>
        {active ? "Expanding…" : "Expand network"}
      </button>
      <span className="rg-expand-status" role="status">
        {error ?? status ?? "Adds papers the session's papers cite, papers citing them, and deeper search results."}
      </span>
    </div>
  );
}

function PaperList({
  ids,
  nodes,
  note,
  onPick,
}: {
  ids: string[];
  nodes: Map<string, ResearchMapNode>;
  note: (node: ResearchMapNode) => string;
  onPick: (paperId: string) => void;
}) {
  return (
    <ol className="rg-paper-list">
      {ids.map((id) => {
        const node = nodes.get(id);
        if (!node) return null;
        return (
          <li key={id}>
            <button className="hub-text-button" onClick={() => onPick(id)}>
              {node.title}
            </button>
            <span>
              {node.year ?? "Undated"} · {note(node)}
              {node.read === false ? "" : " · read"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function YearBars({ map }: { map: ResearchMap }) {
  const buckets = map.timeline;
  if (buckets.length < 2) return null;
  const first = buckets[0].year;
  const last = buckets[buckets.length - 1].year;
  const counts = new Map(buckets.map((b) => [b.year, b.paper_ids.length]));
  const span = last - first + 1;
  const peak = Math.max(...counts.values());
  const width = 100 / span;
  return (
    <figure className="rg-years">
      <svg viewBox="0 0 100 30" preserveAspectRatio="none" role="img" aria-label={`Papers per year, ${first} to ${last}`}>
        {Array.from({ length: span }, (_, i) => {
          const n = counts.get(first + i) ?? 0;
          const h = (n / peak) * 28;
          return (
            <rect key={i} x={i * width + width * 0.1} y={30 - h} width={width * 0.8} height={h}>
              <title>
                {first + i}: {n} papers
              </title>
            </rect>
          );
        })}
      </svg>
      <figcaption>
        <span>{first}</span>
        <span>Papers per year</span>
        <span>{last}</span>
      </figcaption>
    </figure>
  );
}

/** Themes, foundations and frontier of the session's citation network. */
export function FieldInsightPanel({
  map,
  onPick,
  onColorByTheme,
}: {
  map: ResearchMap;
  onPick: (paperId: string) => void;
  onColorByTheme: () => void;
}) {
  const insight = map.insight;
  if (!insight) return null;
  const nodes = new Map(map.nodes.map((node) => [node.paper_id, node]));
  return (
    <section className="rg-insight" aria-label="Field insight">
      <h3>Field insight</h3>
      <p className="rg-insight-summary">{insight.summary}</p>
      <div className="rg-insight-grid">
        <div>
          <h4>Themes</h4>
          {insight.themes.length ? (
            <ul className="rg-themes">
              {insight.themes.map((theme, index) => (
                <li key={theme.id}>
                  <button className="hub-text-button" onClick={onColorByTheme}>
                    <span
                      className="rg-dot"
                      style={{ background: THEME_COLORS[index % THEME_COLORS.length] }}
                    />
                    {theme.label}
                  </button>
                  <span>
                    {theme.paper_ids.length} papers ({theme.read_count} read)
                    {theme.earliest_year ? ` · ${theme.earliest_year}–${theme.latest_year}` : ""}
                    {theme.emerging ? " · emerging" : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="hub-note">Themes appear once enough papers cite each other. Expand the network to find more.</p>
          )}
        </div>
        <div>
          <h4>Foundations</h4>
          {insight.foundation_ids.length ? (
            <PaperList
              ids={insight.foundation_ids}
              nodes={nodes}
              note={(node) => `cited by ${node.in_network_citations ?? 0} papers here`}
              onPick={onPick}
            />
          ) : (
            <p className="hub-note">No paper is cited by two or more papers in this network yet.</p>
          )}
        </div>
        <div>
          <h4>Frontier</h4>
          {insight.frontier_ids.length ? (
            <PaperList
              ids={insight.frontier_ids}
              nodes={nodes}
              note={(node) => `builds on ${node.cites_in_network ?? 0} papers here`}
              onPick={onPick}
            />
          ) : (
            <p className="hub-note">No recent paper cites this network yet.</p>
          )}
        </div>
      </div>
      <YearBars map={map} />
    </section>
  );
}
