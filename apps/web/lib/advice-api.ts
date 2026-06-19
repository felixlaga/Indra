import type { ResearchAdvice } from "@/lib/advice-types";

const API_URL = (
  process.env.NEXT_PUBLIC_ERLA_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export async function getResearchAdvice(sessionId: string): Promise<ResearchAdvice> {
  const response = await fetch(`${API_URL}/sessions/${sessionId}/analysis`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `ERLA API request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload.detail != null) message = String(payload.detail);
    } catch {
      // Preserve the status-based message when the response is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as ResearchAdvice;
}
