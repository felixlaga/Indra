import type {
  Branch,
  ClaimAutoValidationResult,
  ClaimInspection,
  Paper,
  Project,
  ProjectCreate,
  ResearchMap,
  ResearchSession,
  SessionCreate,
  SessionSnapshot,
} from "@/lib/types";

const API_URL = (
  process.env.NEXT_PUBLIC_INDRA_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const API_KEY = process.env.NEXT_PUBLIC_INDRA_API_KEY?.trim();

export function indraAuthHeaders(): HeadersInit {
  return API_KEY ? { "X-Indra-API-Key": API_KEY } : {};
}

export function indraUrl(path: string): string {
  return `${API_URL}${path}`;
}

export function indraUrlWithApiKey(path: string): string {
  const url = new URL(indraUrl(path));
  if (API_KEY) url.searchParams.set("api_key", API_KEY);
  return url.toString();
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(indraUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...indraAuthHeaders(),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Indra API request failed with status ${response.status}`;
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const indraApi = {
  baseUrl: API_URL,
  listProjects: () => request<Project[]>("/projects"),
  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),
  createProject: (payload: ProjectCreate) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listSessions: () => request<ResearchSession[]>("/sessions"),
  createSession: (payload: SessionCreate) =>
    request<ResearchSession>("/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSessionSnapshot: (sessionId: string) =>
    request<SessionSnapshot>(`/sessions/${sessionId}/state`),
  getResearchMap: (sessionId: string) =>
    request<ResearchMap>(`/sessions/${sessionId}/map`),
  runSessionAction: (
    sessionId: string,
    action: "start" | "pause" | "resume" | "cancel",
  ) =>
    request<ResearchSession>(`/sessions/${sessionId}/${action}`, {
      method: "POST",
    }),
  continueBranch: (branchId: string) =>
    request<Branch>(`/branches/${branchId}/continue`, { method: "POST" }),
  pruneBranch: (branchId: string) =>
    request<Branch>(`/branches/${branchId}/prune`, { method: "POST" }),
  getPaper: (paperId: string) => request<Paper>(`/papers/${paperId}`),
  getClaimInspection: (claimId: string) =>
    request<ClaimInspection>(`/claims/${claimId}/inspection`),
  autoValidateClaim: (
    claimId: string,
    payload: { top_k?: number; min_score?: number; include_session_papers?: boolean } = {},
  ) =>
    request<ClaimAutoValidationResult>(`/claims/${claimId}/validate/auto`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
