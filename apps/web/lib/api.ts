import type { ResearchAdvice } from "@/lib/advice-types";
import type { ExportCatalog } from "@/lib/export-types";
import type {
  Branch,
  ClaimAutoValidationResult,
  ClaimInspection,
  Paper,
  PaperChunk,
  Project,
  ProjectCreate,
  ResearchMap,
  ResearchSession,
  SessionCreate,
  SessionSnapshot,
  EventRecord,
  AuthStatus,
} from "@/lib/types";

// The browser talks only to this app; it forwards to the API server-side with the
// signed-in user's token, so no API address, key or token reaches page code.
const API_URL = "/api/indra";

export function indraUrl(path: string): string {
  return `${API_URL}${path}`;
}

/** Same-origin download link; the sign-in cookie goes with it. */
export function exportDownloadUrl(sessionId: string, format: string): string {
  return indraUrl(`/sessions/${sessionId}/exports/${format}`);
}

/** With accounts enabled, an expired or missing sign-in sends the user to sign in. */
export function redirectToSignIn(detail: unknown): boolean {
  const accounts =
    typeof detail === "object" && detail !== null && (detail as { mode?: unknown }).mode === "accounts";
  if (!accounts || typeof window === "undefined") return false;
  if (window.location.pathname !== "/login") {
    const next = `${window.location.pathname}${window.location.search}`;
    window.location.assign(`/login?next=${encodeURIComponent(next)}`);
  }
  return true;
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

async function request<T>(path: string, init?: RequestInit, polls = 0): Promise<T> {
  const response = await fetch(indraUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    // Read the body once: json() consumes it even when parsing fails.
    const body = await response.text();
    let detail: unknown = body;
    try {
      detail = JSON.parse(body);
    } catch {
      // Keep non-JSON details while retaining the HTTP status below.
    }
    if (response.status === 401) redirectToSignIn(detail);
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Indra API request failed with status ${response.status}`;
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (response.status === 202) {
    const pending = await response.json();
    if (!polls) throw new ApiError(pending.detail || "Research view is still queued. Start the view worker, then retry.", 202, pending);
    await new Promise<void>((resolve, reject) => {
      const signal = init?.signal;
      if (signal?.aborted) { reject(signal.reason); return; }
      const abort = () => { clearTimeout(timer); reject(signal?.reason); };
      const timer = setTimeout(() => { signal?.removeEventListener("abort", abort); resolve(); }, 1000);
      signal?.addEventListener("abort", abort, { once: true });
    });
    return request<T>(path, init, polls - 1);
  }
  return (await response.json()) as T;
}

export const indraApi = {
  baseUrl: API_URL,
  getAuthStatus: () => request<AuthStatus>("/auth/me"),
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
    request<SessionSnapshot>(`/sessions/${sessionId}/state?compact=true`),
  getResearchMap: (sessionId: string, signal?: AbortSignal) =>
    request<ResearchMap>(`/sessions/${sessionId}/map`, { signal }, 60),
  getResearchAdvice: (sessionId: string, signal?: AbortSignal) =>
    request<ResearchAdvice>(`/sessions/${sessionId}/analysis`, { signal }, 60),
  retryResearchViews: (sessionId: string) =>
    request<{status: string}>(`/sessions/${sessionId}/views/retry`, { method: "POST" }),
  getOlderEvents: (sessionId: string, before: number) =>
    request<EventRecord[]>(`/sessions/${sessionId}/events?before=${before}&limit=200`),
  getExportCatalog: (sessionId: string) =>
    request<ExportCatalog>(`/sessions/${sessionId}/exports`),
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
  getPaperChunks: (paperId: string) => request<PaperChunk[]>(`/papers/${paperId}/chunks`),
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

export const erlaApi = indraApi;

async function authRequest(action: "login" | "register" | "logout", body?: unknown) {
  const response = await fetch(`/api/auth/${action}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!response.ok && response.status !== 204) {
    const detail = await response.json().catch(() => ({}));
    const message = Array.isArray(detail?.detail)
      ? detail.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(" ")
      : detail?.detail;
    throw new ApiError(message || `Request failed with status ${response.status}`, response.status, detail);
  }
}

export const authApi = {
  login: (email: string, password: string) => authRequest("login", { email, password }),
  register: (email: string, password: string, name?: string) =>
    authRequest("register", { email, password, name: name || undefined }),
  logout: () => authRequest("logout"),
};
