"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { validationSummary } from "@/lib/session-hub.js";
import { indraApi } from "@/lib/api";
import { authorNames, formatDate } from "@/lib/format";
import { claimPolicyMessage, evidenceLocationLabel } from "@/lib/validation";
import { StatusBadge } from "@/components/status-badge";
import type { ClaimInspection, PaperChunk, SessionSnapshot } from "@/lib/types";
import type { ResearchAdvice } from "@/lib/advice-types";

type Props = {
  snapshot: SessionSnapshot;
  type: string | null;
  id: string | null;
  select: (type: string, id: string) => void;
  close: () => void;
  advice: ResearchAdvice | null;
  busy: boolean;
  branchAction: (id: string, action: "continue" | "prune") => void;
  refresh: () => void;
};
export function HubInspector(props: Props) {
  const {
    snapshot,
    type,
    id,
    select,
    close,
    advice,
    busy,
    branchAction,
    refresh,
  } = props;
  const [inspection, setInspection] = useState<ClaimInspection | null>(null);
  const [chunks, setChunks] = useState<PaperChunk[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [retry, setRetry] = useState(0);
  const targetClaim = snapshot.claims.find((claim) => claim.id === id);
  const evidenceVersion = snapshot.claim_evidence.filter(
    (item) => item.claim_id === id,
  ).length;
  useEffect(() => {
    let active = true;
    setInspection(null);
    setChunks(null);
    setError(null);
    setLoading(false);
    if (!id || !["claim", "paper"].includes(type || "")) return;
    setLoading(true);
    const request =
      type === "claim"
        ? indraApi.getClaimInspection(id)
        : indraApi.getPaperChunks(id);
    request
      .then((value) => {
        if (active) {
          if (Array.isArray(value)) setChunks(value);
          else setInspection(value);
        }
      })
      .catch((caught) => {
        if (active)
          setError(
            caught instanceof Error
              ? caught.message
              : "Inspector could not load",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, type, retry, targetClaim?.updated_at, evidenceVersion]);
  if (!id || !type)
    return (
      <div className="hub-inspector-empty">
        <p className="eyebrow">Inspector</p>
        <h2>Follow the evidence</h2>
        <p>
          Select a branch, paper, claim or hypothesis to inspect it here without
          leaving your session.
        </p>
      </div>
    );
  const paper = snapshot.papers.find((entry) => entry.paper_id === id)?.paper;
  const branch = snapshot.branches.find((item) => item.id === id);
  const hypothesis = advice?.hypotheses.find((item) => item.id === id);
  const scoutDecision = snapshot.decisions?.find(
    (item) => item.decision_type === "branch_split" && item.branch_id === id,
  );
  const missing =
    (type === "paper" && !paper) ||
    (type === "branch" && !branch) ||
    (type === "claim" && !targetClaim) ||
    (type === "hypothesis" && advice && !hypothesis);
  return (
    <div className="hub-inspector-content">
      <div className="hub-inspector-header">
        <p className="eyebrow">{type} inspector</p>
        <button
          className="button button-small button-secondary"
          onClick={close}
          aria-label="Close inspector"
        >
          Close
        </button>
      </div>
      {missing && (
        <p role="status">
          This item is not available in this session. Choose another item or
          close the inspector.
        </p>
      )}
      {loading && <p role="status">Loading source details…</p>}
      {error && (
        <p role="alert">
          {error}{" "}
          <button
            className="hub-text-button"
            onClick={() => setRetry((n) => n + 1)}
          >
            Retry inspector
          </button>
        </p>
      )}
      {type === "branch" && branch && (
        <>
          <h2>{branch.label || branch.query}</h2>
          <StatusBadge status={branch.status} />
          <p>{branch.query}</p>
          <h3>Rationale</h3>
          <p>{branch.rationale || "No rationale recorded."}</p>
          <dl className="hub-facts">
            <div>
              <dt>Depth</dt>
              <dd>{branch.depth}</dd>
            </div>
            <div>
              <dt>Mode</dt>
              <dd>{branch.mode.replaceAll("_", " ")}</dd>
            </div>
            <div>
              <dt>Claims</dt>
              <dd>
                {
                  snapshot.claims.filter((claim) => claim.branch_id === id)
                    .length
                }
              </dd>
            </div>
            <div>
              <dt>Validated summaries</dt>
              <dd>
                {
                  snapshot.summaries.filter(
                    (summary) =>
                      summary.branch_id === id &&
                      summary.validation_status === "validated",
                  ).length
                }
              </dd>
            </div>
          </dl>
          {branch.parent_branch_id && (
            <button
              className="hub-text-button"
              onClick={() => select("branch", branch.parent_branch_id!)}
            >
              Inspect parent branch
            </button>
          )}
          {scoutDecision && (
            <>
              <h3>Scout decision</h3>
              <p>
                {scoutDecision.decision} {scoutDecision.rationale}
              </p>
              {scoutDecision.alternatives.map((item, index) => (
                <p key={index} className="hub-note">
                  Not opened: {item.query} — {item.reason}
                </p>
              ))}
            </>
          )}
          {(branch.failure_reason || branch.prune_reason) && (
            <p className="hub-warning">
              {branch.failure_reason || branch.prune_reason}
            </p>
          )}
          <div className="button-row">
            <button
              className="button button-primary button-small"
              disabled={
                busy ||
                snapshot.session.status !== "running" ||
                !["pending", "paused", "failed"].includes(branch.status)
              }
              onClick={() => branchAction(branch.id, "continue")}
            >
              Continue branch
            </button>
            <button
              className="button button-danger button-small"
              disabled={
                busy ||
                !branch.parent_branch_id ||
                ["pruned", "completed"].includes(branch.status)
              }
              onClick={() => branchAction(branch.id, "prune")}
            >
              Prune
            </button>
          </div>
          <h3>Discovered papers</h3>
          {snapshot.papers
            .filter((entry) => entry.branch_id === id)
            .map((entry) => (
              <button
                key={entry.id}
                className="hub-list-button"
                onClick={() => select("paper", entry.paper_id)}
              >
                {entry.paper.title}
              </button>
            ))}
          <h3>Branch history</h3>
          {snapshot.events
            .filter((event) => event.branch_id === id)
            .slice(-8)
            .reverse()
            .map((event) => (
              <p key={event.id}>
                <time>{formatDate(event.created_at)}</time>
                <br />
                {event.event_type.replaceAll("_", " ")}
                {typeof event.payload.message === "string"
                  ? `: ${event.payload.message}`
                  : ""}
              </p>
            ))}
        </>
      )}
      {type === "paper" && paper && (
        <>
          <h2>{paper.title}</h2>
          <p>{authorNames(paper.authors)}</p>
          <dl className="hub-facts">
            <div>
              <dt>Year</dt>
              <dd>{paper.year ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Citations</dt>
              <dd>{paper.citation_count ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Venue</dt>
              <dd>{paper.venue || "Unknown"}</dd>
            </div>
            <div>
              <dt>Full text</dt>
              <dd>
                {chunks === null
                  ? "Not loaded"
                  : chunks.length
                    ? `${chunks.length} passages`
                    : paper.abstract
                      ? "Abstract only"
                      : "No source text available"}
              </dd>
            </div>
          </dl>
          <details open>
            <summary>Abstract</summary>
            <p>{paper.abstract || "No abstract available."}</p>
          </details>
          <h3>Session summaries</h3>
          {snapshot.summaries
            .filter((summary) => summary.paper_id === id)
            .map((summary) => (
              <section className="hub-evidence" key={summary.id}>
                <StatusBadge status={summary.validation_status} />
                <p>{summary.text}</p>
              </section>
            ))}
          {!snapshot.summaries.some((summary) => summary.paper_id === id) && (
            <p>No summary has been saved yet.</p>
          )}
          <h3>Claims</h3>
          {snapshot.claims
            .filter((claim) => claim.paper_id === id)
            .map((claim) => (
              <button
                className="hub-claim-card"
                key={claim.id}
                onClick={() => select("claim", claim.id)}
              >
                <StatusBadge status={claim.status} />
                {claim.claim_text}
              </button>
            ))}
          <details>
            <summary>Source passages ({chunks?.length ?? 0})</summary>
            {chunks?.map((chunk) => (
              <details className="hub-evidence" key={chunk.id}>
                <summary>
                  Page {chunk.page_start ?? "unknown"} · Passage{" "}
                  {chunk.chunk_index + 1}
                </summary>
                <p>{chunk.text}</p>
              </details>
            ))}
          </details>
          <div className="button-row">
            <Link
              className="button button-secondary button-small"
              href={`/papers/${paper.id}`}
            >
              Full paper page
            </Link>
            {paper.url && (
              <a
                className="button button-secondary button-small"
                href={paper.url}
                target="_blank"
                rel="noreferrer"
              >
                External source ↗
              </a>
            )}
          </div>
        </>
      )}
      {type === "claim" && targetClaim && (
        <>
          <h2>{targetClaim.claim_text}</h2>
          <StatusBadge status={targetClaim.status} />
          <p>{claimPolicyMessage(targetClaim.status)}</p>
          <dl className="hub-facts">
            <div>
              <dt>Type</dt>
              <dd>{targetClaim.claim_type.replaceAll("_", " ")}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>
                {targetClaim.confidence == null
                  ? "Unscored"
                  : `${Math.round(targetClaim.confidence * 100)}%`}
              </dd>
            </div>
          </dl>
          {targetClaim.paper_id && (
            <button
              className="hub-text-button"
              onClick={() => select("paper", targetClaim.paper_id!)}
            >
              Inspect source paper →
            </button>
          )}
          {targetClaim.status !== "speculative" &&
            targetClaim.claim_type !== "hypothesis" && (
              <button
                className="button button-secondary button-small"
                disabled={validating || loading}
                onClick={async () => {
                  setValidating(true);
                  setError(null);
                  try {
                    await indraApi.autoValidateClaim(targetClaim.id);
                    refresh();
                    setRetry((n) => n + 1);
                  } catch (caught) {
                    setError(
                      caught instanceof Error
                        ? caught.message
                        : "Validation failed",
                    );
                  } finally {
                    setValidating(false);
                  }
                }}
              >
                {validating ? "Checking evidence…" : "Retrieve and validate"}
              </button>
            )}
          <h3>Source evidence</h3>
          {inspection?.evidence.map((item) => (
            <article className="hub-evidence" key={item.id}>
              <StatusBadge status={item.relation} />
              <p className="hub-note">
                {evidenceLocationLabel(item)} ·{" "}
                {item.source_type.replaceAll("_", " ")}
              </p>
              <blockquote>{item.evidence_text}</blockquote>
              {item.paper_id && (
                <button
                  className="hub-text-button"
                  onClick={() => select("paper", item.paper_id!)}
                >
                  {snapshot.papers.find(
                    (entry) => entry.paper_id === item.paper_id,
                  )?.paper.title || "Inspect evidence source"}{" "}
                  →
                </button>
              )}
            </article>
          ))}
          {inspection && !inspection.evidence.length && (
            <p>No evidence is attached.</p>
          )}
          <h3>Validation history</h3>
          {inspection?.validations
            .slice()
            .reverse()
            .map((trace) => (
              <details key={trace.id} className="hub-evidence">
                <summary>
                  {formatDate(trace.created_at)} ·{" "}
                  {trace.status.replaceAll("_", " ")}
                </summary>
                <p>
                  {trace.validator_type.replaceAll("_", " ")} ·{" "}
                  {trace.evidence_ids.length} evidence passages
                </p>
                <p>{validationSummary(trace.notes)}</p>
              </details>
            ))}
          {inspection && !inspection.validations.length && (
            <p>No validation checks recorded.</p>
          )}
        </>
      )}
      {type === "hypothesis" && !advice && (
        <p role="status">Loading hypothesis context from the advisor…</p>
      )}
      {type === "hypothesis" && hypothesis && (
        <>
          <h2>{hypothesis.text}</h2>
          <StatusBadge status="speculative" />
          <p>
            {hypothesis.source === "model"
              ? "Proposed by session synthesis from claims in several papers. "
              : "Derived from an open-problem signal. "}
            Research proposal, not an established result. Scores are advisor
            heuristics, not calibrated probabilities.
          </p>
          <h3>Rationale</h3>
          <p>{hypothesis.rationale}</p>
          <dl className="hub-facts">
            <div>
              <dt>Risk</dt>
              <dd>{hypothesis.risk}</dd>
            </div>
            <div>
              <dt>Testability signal</dt>
              <dd>{hypothesis.testability.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Confidence signal</dt>
              <dd>{hypothesis.confidence.toFixed(2)}</dd>
            </div>
          </dl>
          <h3>Missing evidence</h3>
          <ul>
            {hypothesis.missing_evidence.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
          <h3>Suggested next steps</h3>
          <ol>
            {hypothesis.next_steps.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ol>
          <h3>Supporting context</h3>
          {hypothesis.supporting_claim_ids.map((claimId) => (
            <button
              key={claimId}
              className="hub-list-button"
              onClick={() => select("claim", claimId)}
            >
              {snapshot.claims.find((claim) => claim.id === claimId)
                ?.claim_text || "Inspect claim"}
            </button>
          ))}
          {hypothesis.supporting_paper_ids.map((paperId) => (
            <button
              key={paperId}
              className="hub-list-button"
              onClick={() => select("paper", paperId)}
            >
              {snapshot.papers.find((entry) => entry.paper_id === paperId)
                ?.paper.title || "Inspect paper"}
            </button>
          ))}
          {!!hypothesis.contradicting_claim_ids?.length && (
            <>
              <h3>Contradicting claims</h3>
              {hypothesis.contradicting_claim_ids.map((claimId) => (
                <button
                  key={claimId}
                  className="hub-list-button"
                  onClick={() => select("claim", claimId)}
                >
                  {snapshot.claims.find((claim) => claim.id === claimId)
                    ?.claim_text || "Inspect claim"}
                </button>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
