"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import { indraApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ClaimInspection } from "@/lib/types";
import {
  claimPolicyMessage,
  evidenceLocationLabel,
  parseValidationNotes,
} from "@/lib/validation";

import styles from "./claim-page.module.css";

export function ClaimPageClient({ claimId }: { claimId: string }) {
  const [inspection, setInspection] = useState<ClaimInspection | null>(null);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultNotice, setResultNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setInspection(await indraApi.getClaimInspection(claimId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Claim could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [claimId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function autoValidate() {
    setValidating(true);
    setError(null);
    setResultNotice(null);
    try {
      const result = await indraApi.autoValidateClaim(claimId, {
        top_k: 5,
        min_score: 0.15,
        include_session_papers: true,
      });
      setInspection(result.inspection);
      setResultNotice(
        `Reviewed ${result.candidates_considered} candidate passages and stored ${result.evidence_retrieved} evidence passages.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Automatic validation failed");
    } finally {
      setValidating(false);
    }
  }

  if (loading) {
    return (
      <>
        <AppHeader title="Loading claim…" />
        <main className="page-shell"><div className="detail-skeleton" /></main>
      </>
    );
  }

  if (error && !inspection) {
    return (
      <>
        <AppHeader title="Claim unavailable" />
        <main className="page-shell">
          <ErrorPanel message={error} onRetry={() => void load()} />
        </main>
      </>
    );
  }

  if (!inspection) return null;
  const { claim, evidence, validations, paper } = inspection;
  const canAutoValidate = claim.status !== "speculative" && claim.claim_type !== "hypothesis";

  return (
    <>
      <AppHeader
        eyebrow={claim.claim_type.replaceAll("_", " ")}
        title={claim.claim_text}
        description="Inspect the source passages and validation decisions before this claim is used downstream."
        actions={
          <div className="button-row">
            <Link className="button button-secondary" href={`/sessions/${claim.session_id}`}>
              Back to session
            </Link>
            {canAutoValidate ? (
              <button
                className="button button-primary"
                type="button"
                onClick={() => void autoValidate()}
                disabled={validating}
              >
                {validating ? "Retrieving evidence…" : "Retrieve and validate"}
              </button>
            ) : null}
          </div>
        }
      />
      <main className={`page-shell ${styles.layout}`}>
        <section className={styles.main}>
          {error ? <ErrorPanel message={error} /> : null}
          {resultNotice ? <div className={styles.resultNotice}>{resultNotice}</div> : null}

          <div className={styles.policy}>
            <StatusBadge status={claim.status} />
            <p>{claimPolicyMessage(claim.status)}</p>
          </div>

          <section className={styles.panel}>
            <div className={styles.heading}>
              <div>
                <p className="eyebrow">Evidence passage viewer</p>
                <h2>Source evidence</h2>
                <p>{evidence.length} stored passage{evidence.length === 1 ? "" : "s"}</p>
              </div>
            </div>
            {evidence.length === 0 ? (
              <EmptyState
                title="No evidence attached"
                description="Run evidence retrieval or supply explicit source passages before treating this claim as factual."
              />
            ) : (
              <div className={styles.evidenceList}>
                {evidence.map((item) => (
                  <article className={styles.evidenceCard} key={item.id}>
                    <div className={styles.evidenceTop}>
                      <StatusBadge status={item.relation} compact />
                      <span className={styles.muted}>
                        {item.score == null ? "Unscored" : `${Math.round(item.score * 100)}% relation score`}
                      </span>
                    </div>
                    <div className={styles.evidenceMeta}>
                      <span>{evidenceLocationLabel(item)}</span>
                      <span>{item.source_type.replaceAll("_", " ")}</span>
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                    <p className={styles.evidenceText}>{item.evidence_text}</p>
                    {item.paper_id ? (
                      <Link className={styles.paperLink} href={`/papers/${item.paper_id}`}>
                        Open source paper →
                      </Link>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </section>
        </section>

        <aside className={styles.sidebar}>
          <section className={styles.panel}>
            <div className={styles.heading}>
              <div>
                <p className="eyebrow">Claim state</p>
                <h2>Validation summary</h2>
              </div>
            </div>
            <div className={styles.metrics}>
              <div className={styles.metric}>
                <span>Status</span>
                <strong>{claim.status.replaceAll("_", " ")}</strong>
              </div>
              <div className={styles.metric}>
                <span>Confidence</span>
                <strong>{claim.confidence == null ? "—" : `${Math.round(claim.confidence * 100)}%`}</strong>
              </div>
              <div className={styles.metric}>
                <span>Evidence</span>
                <strong>{evidence.length}</strong>
              </div>
            </div>
            {paper ? (
              <div className={styles.traceDetails}>
                <span>Primary paper</span>
                <Link className={styles.paperLink} href={`/papers/${paper.id}`}>
                  {paper.title}
                </Link>
              </div>
            ) : null}
          </section>

          <section className={styles.panel}>
            <div className={styles.heading}>
              <div>
                <p className="eyebrow">Audit trail</p>
                <h2>Validation trace</h2>
                <p>{validations.length} validation run{validations.length === 1 ? "" : "s"}</p>
              </div>
            </div>
            {validations.length === 0 ? (
              <EmptyState
                title="No validation trace"
                description="Every evidence-based decision will be preserved here rather than overwriting its history."
              />
            ) : (
              <div className={styles.traceList}>
                {[...validations].reverse().map((trace) => {
                  const notes = parseValidationNotes(trace);
                  return (
                    <article className={styles.traceCard} key={trace.id}>
                      <div className={styles.traceTop}>
                        <StatusBadge status={trace.status} compact />
                        <time className={styles.muted}>{formatDate(trace.created_at)}</time>
                      </div>
                      <div className={styles.traceMeta}>
                        <span>{trace.validator_type.replaceAll("_", " ")}</span>
                        <span>{trace.evidence_ids.length} evidence IDs</span>
                        <span>{trace.confidence == null ? "unscored" : `${Math.round(trace.confidence * 100)}%`}</span>
                      </div>
                      {notes ? (
                        <div className={styles.traceDetails}>
                          {notes.strategy ? <span>Strategy: {notes.strategy}</span> : null}
                          {notes.candidates_considered != null ? (
                            <p>{notes.candidates_considered} passages considered; {notes.retrieved?.length ?? 0} retained.</p>
                          ) : notes.raw ? (
                            <code>{notes.raw}</code>
                          ) : null}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </aside>
      </main>
    </>
  );
}
