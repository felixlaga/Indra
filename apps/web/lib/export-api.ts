import type { ExportCatalog } from "@/lib/export-types";

export const INDRA_API_URL = (
  process.env.NEXT_PUBLIC_INDRA_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export async function getExportCatalog(sessionId: string): Promise<ExportCatalog> {
  const response = await fetch(`${INDRA_API_URL}/sessions/${sessionId}/exports`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Indra API request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload.detail != null) message = String(payload.detail);
    } catch {
      // Preserve the status-derived message for non-JSON failures.
    }
    throw new Error(message);
  }
  return (await response.json()) as ExportCatalog;
}

export function exportDownloadUrl(sessionId: string, format: string): string {
  return `${INDRA_API_URL}/sessions/${sessionId}/exports/${format}`;
}
