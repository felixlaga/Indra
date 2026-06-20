import type { ExportCatalog } from "@/lib/export-types";

export const ERLA_API_URL = (
  process.env.NEXT_PUBLIC_ERLA_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export async function getExportCatalog(sessionId: string): Promise<ExportCatalog> {
  const response = await fetch(`${ERLA_API_URL}/sessions/${sessionId}/exports`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `ERLA API request failed with status ${response.status}`;
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
  return `${ERLA_API_URL}/sessions/${sessionId}/exports/${format}`;
}
