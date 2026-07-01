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

export function ClaimPageClient({ claimId }: { claimId: string }) {
  const [inspection, setInspection] = useState<ClaimInspection | null>(null);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
    setNotice(null);
    try {
      const result = await indraApi.autoValidateClaim(claimId, {
        top_k: 5,
        min_score: 0.15,
        include_session_papers: true,
      });
      setInspection(result.inspection);
      setNotice(`Stored ${result.evidence_retrieved} evidence passages from ${result.candidates_considered} candidates.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Automatic validation failed");
    } finally {
      setValidating(false);
    }
  }

  if (loading) {
    return <main className="page-shell"><p>Loading claim...</p></main>;
  }
  if (!inspection) {
    return <main className="page-shell"><ErrorPanel message={error || "Claim could not be loaded"} onRetry={() => void load()} /></main>;
  }

  const { claim, evidence } = inspection;

  return (
    <>
      <AppHeader
        eyebrow="Claim inspection"
        title="Evidence ledger"
        description="Inspect the claim, attached evidence passages, validation status, and policy boundary."
        actions={<button className="button button-primary" type="button" disabled={validating} onClick={() => void autoValidate()}>{validating ? "Validating..." : "Auto-validate"}</button>}
      />
      <main className="page-shell">
        {error ? <ErrorPanel message={error} onRetry={() => void load()} /> : null}
        {notice ? <p className="stream-warning">{notice}</p> : null}
        <section className="inspector-content">
          <div className="inspector-title-row">
            <div>
              <p className="eyebrow">Atomic claim</p>
              <h1>{claim.claim_text}</h1>
            </div>
            <StatusBadge status={claim.status} />
          </div>
          <dl className="metric-grid metric-grid-3 compact-metrics">
            <div><dt>Type</dt><dd>{claim.claim_type.replaceAll("_", " ")}</dd></div>
            <div><dt>Confidence</dt><dd>{claim.confidence == null ? "not scored" : `${Math.round(claim.confidence * 100)}%`}</dd></div>
            <div><dt>Updated</dt><dd>{formatDate(claim.updated_at)}</dd></div>
          </dl>
          {claim.paper_id ? <Link className="button button-secondary button-small" href={`/papers/${claim.paper_id}`}>Open source paper</Link> : null}
        </section>

        <section className="dashboard-drawer">
          <h2>Evidence</h2>
          {evidence.length === 0 ? (
            <EmptyState title="No evidence attached" description="Run automatic validation or add evidence through the API." />
          ) : (
            <div className="event-log">
              {evidence.map((item) => (
                <article className="event-row" key={item.id}>
                  <div>
                    <strong>{item.relation.replaceAll("_", " ")}</strong>
                    <p>{item.evidence_text}</p>
                    <small>{item.source_type.replaceAll("_", " ")} - {formatDate(item.created_at)}</small>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </>
  );
}
