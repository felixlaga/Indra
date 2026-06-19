"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorPanel } from "@/components/error-panel";
import { exportDownloadUrl, getExportCatalog } from "@/lib/export-api";
import type { ExportCatalog, ExportDescriptor } from "@/lib/export-types";

import styles from "./export-center-page.module.css";

const GROUPS: Array<{ title: string; formats: string[] }> = [
  {
    title: "Bibliographies",
    formats: ["bibtex", "ris", "annotated-bibliography"],
  },
  {
    title: "Research documents",
    formats: ["report-markdown", "literature-review-latex"],
  },
  {
    title: "Data exports",
    formats: ["claim-ledger-csv", "claim-ledger-json", "research-map-json"],
  },
];

function ArtifactCard({
  artifact,
  sessionId,
}: {
  artifact: ExportDescriptor;
  sessionId: string;
}) {
  return (
    <article className={styles.card}>
      <div className={styles.cardHeading}>
        <div>
          <h3>{artifact.label}</h3>
          <p>{artifact.description}</p>
        </div>
        <span>{artifact.media_type.split(";")[0]}</span>
      </div>
      <dl>
        <div><dt>Filename</dt><dd>{artifact.filename}</dd></div>
        <div><dt>Validation</dt><dd>{artifact.preserves_validation_status ? "Preserved" : "Not guaranteed"}</dd></div>
      </dl>
      <a
        className="button button-primary button-small"
        href={exportDownloadUrl(sessionId, artifact.format)}
      >
        Download
      </a>
    </article>
  );
}

export function ExportCenterPageClient({ sessionId }: { sessionId: string }) {
  const [catalog, setCatalog] = useState<ExportCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCatalog(await getExportCatalog(sessionId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Export catalog could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const byFormat = useMemo(
    () => new Map(catalog?.artifacts.map((artifact) => [artifact.format, artifact]) ?? []),
    [catalog],
  );

  if (loading) {
    return (
      <>
        <AppHeader title="Loading export center…" />
        <main className="page-shell"><div className="detail-skeleton" /></main>
      </>
    );
  }

  if (error && !catalog) {
    return (
      <>
        <AppHeader title="Export center unavailable" />
        <main className="page-shell"><ErrorPanel message={error} onRetry={() => void load()} /></main>
      </>
    );
  }

  if (!catalog) return null;

  return (
    <>
      <AppHeader
        eyebrow="Phase 8 exports"
        title="Leave ERLA with reusable research artifacts"
        description="Download bibliographies, reports, literature-review outlines, claim ledgers, and the complete research map. Claim-bearing artifacts preserve validation status and explicitly label unsupported output."
        actions={
          <div className="button-row">
            <Link className="button button-secondary" href={`/sessions/${sessionId}/advisor`}>Research advisor</Link>
            <Link className="button button-secondary" href={`/sessions/${sessionId}`}>Back to session</Link>
          </div>
        }
      />
      <main className={`page-shell ${styles.layout}`}>
        {error ? <ErrorPanel message={error} /> : null}
        <section className={styles.notice}>
          <strong>Validation policy</strong>
          <p>
            Claim ledgers, reports, outlines, and annotated bibliographies retain each claim's status. Unsupported, contradicted, speculative, and unreviewed claims remain visibly labelled and are not silently converted into factual prose.
          </p>
        </section>

        {GROUPS.map((group) => {
          const artifacts = group.formats
            .map((format) => byFormat.get(format))
            .filter((artifact): artifact is ExportDescriptor => Boolean(artifact));
          return (
            <section className={styles.group} key={group.title}>
              <div className={styles.groupHeading}>
                <h2>{group.title}</h2>
                <span>{artifacts.length} formats</span>
              </div>
              {artifacts.length === 0 ? (
                <EmptyState title="No exports available" description="This export group is not available for the current session." />
              ) : (
                <div className={styles.grid}>
                  {artifacts.map((artifact) => (
                    <ArtifactCard artifact={artifact} sessionId={sessionId} key={artifact.format} />
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </main>
    </>
  );
}
