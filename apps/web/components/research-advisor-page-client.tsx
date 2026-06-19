"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { StatusBadge } from "@/components/status-badge";
import type {
  AdvisorRecommendation,
  ContradictionCandidate,
  HypothesisProposal,
  ResearchAdvice,
  ResearchGap,
} from "@/lib/advice-types";
import { getResearchAdvice } from "@/lib/advice-api";

import styles from "./research-advisor-page.module.css";

type Tab = "recommendations" | "contradictions" | "gaps" | "hypotheses";

function SourceLinks({
  sessionId,
  claimIds,
  paperIds,
}: {
  sessionId: string;
  claimIds: string[];
  paperIds: string[];
}) {
  return (
    <div className={styles.links}>
      {claimIds.map((claimId) => (
        <Link key={claimId} href={`/claims/${claimId}`}>Claim evidence</Link>
      ))}
      {paperIds.map((paperId) => (
        <Link key={paperId} href={`/papers/${paperId}`}>Source paper</Link>
      ))}
      <Link href={`/sessions/${sessionId}/map`}>Research map</Link>
    </div>
  );
}

function RecommendationCard({
  item,
  sessionId,
}: {
  item: AdvisorRecommendation;
  sessionId: string;
}) {
  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <h3>{item.title}</h3>
        <StatusBadge status={item.priority} compact />
      </div>
      <p className={styles.action}>{item.action}</p>
      <p>{item.rationale}</p>
      <SourceLinks
        sessionId={sessionId}
        claimIds={item.claim_ids}
        paperIds={item.paper_ids}
      />
    </article>
  );
}

function ContradictionCard({
  item,
  sessionId,
}: {
  item: ContradictionCandidate;
  sessionId: string;
}) {
  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <h3>{item.kind.replaceAll("_", " ")}</h3>
        <StatusBadge status={item.status} compact />
      </div>
      <p className={styles.action}>{item.description}</p>
      <p>{item.rationale}</p>
      <div className={styles.score}>Signal strength: {Math.round(item.score * 100)}%</div>
      <SourceLinks
        sessionId={sessionId}
        claimIds={item.claim_ids}
        paperIds={item.paper_ids}
      />
    </article>
  );
}

function GapCard({ item, sessionId }: { item: ResearchGap; sessionId: string }) {
  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <h3>{item.title}</h3>
        <StatusBadge status={item.gap_type} compact />
      </div>
      <p className={styles.action}>{item.description}</p>
      <p>{item.caveat}</p>
      <div className={styles.score}>Priority signal: {Math.round(item.score * 100)}%</div>
      <SourceLinks
        sessionId={sessionId}
        claimIds={item.claim_ids}
        paperIds={item.paper_ids}
      />
    </article>
  );
}

function HypothesisCard({
  item,
  sessionId,
}: {
  item: HypothesisProposal;
  sessionId: string;
}) {
  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <h3>Speculative proposal</h3>
        <StatusBadge status={item.status} compact />
      </div>
      <p className={styles.action}>{item.text}</p>
      <p>{item.rationale}</p>
      <div className={styles.hypothesisMetrics}>
        <span>Confidence {Math.round(item.confidence * 100)}%</span>
        <span>Testability {Math.round(item.testability * 100)}%</span>
        <span>Risk {item.risk}</span>
      </div>
      <section className={styles.subsection}>
        <h4>Missing evidence</h4>
        <ul>{item.missing_evidence.map((entry) => <li key={entry}>{entry}</li>)}</ul>
      </section>
      <section className={styles.subsection}>
        <h4>Next steps</h4>
        <ol>{item.next_steps.map((entry) => <li key={entry}>{entry}</li>)}</ol>
      </section>
      <SourceLinks
        sessionId={sessionId}
        claimIds={item.supporting_claim_ids}
        paperIds={item.supporting_paper_ids}
      />
    </article>
  );
}

export function ResearchAdvisorPageClient({ sessionId }: { sessionId: string }) {
  const [advice, setAdvice] = useState<ResearchAdvice | null>(null);
  const [tab, setTab] = useState<Tab>("recommendations");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAdvice(await getResearchAdvice(sessionId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Research advice could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const counts = useMemo(() => {
    if (!advice) return {} as Record<Tab, number>;
    return {
      recommendations: advice.recommendations.length,
      contradictions: advice.contradictions.length,
      gaps: advice.gaps.length,
      hypotheses: advice.hypotheses.length,
    };
  }, [advice]);

  if (loading) {
    return (
      <>
        <AppHeader title="Loading research advisor…" />
        <main className="page-shell"><div className="detail-skeleton" /></main>
      </>
    );
  }

  if (error && !advice) {
    return (
      <>
        <AppHeader title="Research advisor unavailable" />
        <main className="page-shell"><ErrorPanel message={error} onRetry={() => void load()} /></main>
      </>
    );
  }

  if (!advice) return null;

  return (
    <>
      <AppHeader
        eyebrow="Research advisor"
        title="Gaps, contradictions, and next research actions"
        description="Every item below is an inspectable session-level signal. Candidates are not silently promoted into field-wide claims."
        actions={
          <div className="button-row">
            <Link className="button button-secondary" href={`/sessions/${sessionId}/map`}>Research map</Link>
            <Link className="button button-secondary" href={`/sessions/${sessionId}`}>Back to session</Link>
          </div>
        }
      />
      <main className={`page-shell ${styles.layout}`}>
        {error ? <ErrorPanel message={error} /> : null}

        <section className={styles.overview}>
          <div>
            <p className="eyebrow">Current assessment</p>
            <p>{advice.overview.text}</p>
            <ul>
              {advice.overview.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
            </ul>
          </div>
          <div className={styles.metrics}>
            <div><span>Contradictions</span><strong>{advice.overview.contradiction_count}</strong></div>
            <div><span>Evidence gaps</span><strong>{advice.overview.gap_count}</strong></div>
            <div><span>Weak claims</span><strong>{advice.overview.weak_evidence_count}</strong></div>
            <div><span>Open signals</span><strong>{advice.overview.open_problem_count}</strong></div>
            <div><span>Hypotheses</span><strong>{advice.overview.hypothesis_count}</strong></div>
          </div>
        </section>

        <nav className={styles.tabs} aria-label="Research advisor sections">
          {(["recommendations", "contradictions", "gaps", "hypotheses"] as Tab[]).map((item) => (
            <button
              type="button"
              key={item}
              className={tab === item ? styles.activeTab : ""}
              onClick={() => setTab(item)}
            >
              {item} <span>{counts[item]}</span>
            </button>
          ))}
        </nav>

        <section className={styles.grid}>
          {tab === "recommendations" && advice.recommendations.map((item) => (
            <RecommendationCard key={item.id} item={item} sessionId={sessionId} />
          ))}
          {tab === "contradictions" && advice.contradictions.map((item) => (
            <ContradictionCard key={item.id} item={item} sessionId={sessionId} />
          ))}
          {tab === "gaps" && advice.gaps.map((item) => (
            <GapCard key={item.id} item={item} sessionId={sessionId} />
          ))}
          {tab === "hypotheses" && advice.hypotheses.map((item) => (
            <HypothesisCard key={item.id} item={item} sessionId={sessionId} />
          ))}
          {counts[tab] === 0 ? (
            <EmptyState
              title={`No ${tab.replaceAll("_", " ")} found`}
              description="The current durable session state does not contain a signal in this category."
            />
          ) : null}
        </section>

        <section className={styles.weakEvidence}>
          <div className={styles.sectionHeading}>
            <div><p className="eyebrow">Claim triage</p><h2>Weak-evidence queue</h2></div>
            <span>{advice.weak_evidence.length} claims</span>
          </div>
          {advice.weak_evidence.length === 0 ? (
            <EmptyState title="No weak-evidence claims" description="All current claims have attached evidence and no weak status." />
          ) : (
            <div className={styles.tableWrap}>
              <table>
                <thead><tr><th>Claim</th><th>Status</th><th>Evidence</th><th>Priority</th><th /></tr></thead>
                <tbody>
                  {advice.weak_evidence.map((item) => (
                    <tr key={item.claim_id}>
                      <td>{item.claim_text}<small>{item.reason}</small></td>
                      <td><StatusBadge status={item.claim_status} compact /></td>
                      <td>{item.evidence_count}</td>
                      <td><StatusBadge status={item.priority} compact /></td>
                      <td><Link href={`/claims/${item.claim_id}`}>Inspect</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </>
  );
}
