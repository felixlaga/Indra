"use client";
import { useState } from "react";
import { buildBranchTree } from "@/lib/tree.js";
import { timelineGroups, uniquePapers } from "@/lib/session-hub.js";
import { StatusBadge } from "@/components/status-badge";
import { authorNames } from "@/lib/format";
import type { Branch, Paper, SessionSnapshot } from "@/lib/types";
import type { ResearchAdvice } from "@/lib/advice-types";

type Select = (type: string, id: string) => void;
function PaperRow({ paper, select }: { paper: Paper; select: Select }) {
  return (
    <button className="hub-paper" onClick={() => select("paper", paper.id)}>
      <strong>{paper.title}</strong>
      <span>
        {authorNames(paper.authors)} · {paper.year ?? "Undated"}
      </span>
      <small>
        {paper.citation_count == null
          ? "Citation count unavailable"
          : `${paper.citation_count} citations`}
      </small>
    </button>
  );
}
export function PapersView({
  snapshot,
  select,
}: {
  snapshot: SessionSnapshot;
  select: Select;
}) {
  const papers = uniquePapers(snapshot.papers);
  return (
    <div className="hub-view-content">
      {papers.length ? (
        papers.map((paper) => (
          <PaperRow key={paper.id} paper={paper} select={select} />
        ))
      ) : (
        <p className="hub-note">Papers appear here as research progresses.</p>
      )}
    </div>
  );
}
export function TimelineView({
  snapshot,
  select,
}: {
  snapshot: SessionSnapshot;
  select: Select;
}) {
  const groups = timelineGroups(uniquePapers(snapshot.papers));
  return (
    <div className="hub-view-content">
      <p className="hub-note">
        Publication years, newest first. Undated papers remain visible at the
        end.
      </p>
      {groups.length ? (
        groups.map((group) => (
          <section className="hub-timeline-group" key={group.year ?? "unknown"}>
            <h3>
              {group.year ?? "Undated"}{" "}
              <span>{group.papers.length} papers</span>
            </h3>
            <div>
              {group.papers.map((paper) => (
                <PaperRow key={paper.id} paper={paper} select={select} />
              ))}
            </div>
          </section>
        ))
      ) : (
        <p className="hub-note">
          The publication timeline will populate when papers are found.
        </p>
      )}
    </div>
  );
}

type Node = Branch & { children: Node[] };
function ScoutNode({
  node,
  snapshot,
  select,
  level = 0,
}: {
  node: Node;
  snapshot: SessionSnapshot;
  select: Select;
  level?: number;
}) {
  const papers = uniquePapers(
    snapshot.papers.filter((entry) => entry.branch_id === node.id),
  );
  return (
    <li>
      <article className="hub-scout-node">
        <button
          className="hub-text-button"
          onClick={() => select("branch", node.id)}
        >
          <strong>{node.label || "Branch"}</strong>
          <span>{node.query}</span>
        </button>
        <StatusBadge status={node.status} />
        <p>{node.rationale || "No rationale recorded."}</p>
        <small>
          {papers.length} papers ·{" "}
          {
            snapshot.claims.filter((claim) => claim.branch_id === node.id)
              .length
          }{" "}
          claims
        </small>
      </article>
      {!!papers.length && (
        <details className="hub-scout-papers" open={level === 0}>
          <summary>Discovered papers ({papers.length})</summary>
          {papers.map((paper) => (
            <PaperRow key={paper.id} paper={paper} select={select} />
          ))}
        </details>
      )}
      {!!node.children.length && (
        <ul>
          {node.children.map((child) => (
            <ScoutNode
              key={child.id}
              node={child}
              snapshot={snapshot}
              select={select}
              level={level + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
export function ScoutView({
  snapshot,
  select,
}: {
  snapshot: SessionSnapshot;
  select: Select;
}) {
  const tree = buildBranchTree(snapshot.branches) as Node[];
  return (
    <div className="hub-view-content">
      <p className="hub-note">
        Recorded branch structure and discoveries. Select a branch to inspect
        its rationale and controls.
      </p>
      <ul className="hub-scout-tree">
        {tree.map((node) => (
          <ScoutNode
            key={node.id}
            node={node}
            snapshot={snapshot}
            select={select}
          />
        ))}
      </ul>
    </div>
  );
}
export function ClaimMapView({
  snapshot,
  advice,
  adviceError,
  loading,
  select,
  retry,
}: {
  snapshot: SessionSnapshot;
  advice: ResearchAdvice | null;
  adviceError: string | null;
  loading: boolean;
  select: Select;
  retry: () => void;
}) {
  const [branch, setBranch] = useState("");
  const statuses = [
    "contradicted",
    "needs_review",
    "weakly_supported",
    "supported",
    "not_found",
    "speculative",
  ];
  return (
    <div className="hub-view-content">
      <p className="hub-note">
        Claims grouped by evidence status. Statuses describe the stored checks,
        not scientific consensus.
      </p>
      <label className="hub-topic-filter">
        Topic / branch
        <select
          value={branch}
          onChange={(event) => setBranch(event.target.value)}
        >
          <option value="">All branches</option>
          {snapshot.branches.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label || item.query}
            </option>
          ))}
        </select>
      </label>
      <div className="hub-claim-groups">
        {statuses.map((status) => {
          const claims = snapshot.claims.filter(
            (claim) =>
              claim.status === status &&
              (!branch || claim.branch_id === branch),
          );
          return (
            <section key={status}>
              <h3>
                <StatusBadge status={status} /> <span>{claims.length}</span>
              </h3>
              {claims.slice(0, 30).map((claim) => (
                <button
                  key={claim.id}
                  className="hub-claim-card"
                  onClick={() => select("claim", claim.id)}
                >
                  {claim.claim_text}
                  <small>
                    {snapshot.papers.find(
                      (entry) => entry.paper_id === claim.paper_id,
                    )?.paper.title || "No source paper"}
                  </small>
                </button>
              ))}
              {claims.length > 30 && (
                <p>
                  Showing 30; use the ledger for all {claims.length} claims.
                </p>
              )}
              {!claims.length && (
                <p className="hub-note">No claims in this group.</p>
              )}
            </section>
          );
        })}
      </div>
      <section className="hub-hypotheses">
        <h3>Hypotheses to inspect</h3>
        <p className="hub-note">
          Advisor proposals are speculative prompts for investigation, not
          established results or claims of novelty.
        </p>
        {loading && <p role="status">Loading advisor proposals…</p>}
        {adviceError && (
          <p role="alert">
            {adviceError}{" "}
            <button className="hub-text-button" onClick={retry}>
              Retry proposals
            </button>
          </p>
        )}
        {advice?.hypotheses.map((hypothesis) => (
          <button
            className="hub-claim-card"
            key={hypothesis.id}
            onClick={() => select("hypothesis", hypothesis.id)}
          >
            <StatusBadge status="speculative" />
            {hypothesis.text}
          </button>
        ))}
        {advice && !advice.hypotheses.length && (
          <p>No hypotheses have been proposed for this session.</p>
        )}
      </section>
    </div>
  );
}
