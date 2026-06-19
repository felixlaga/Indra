export type SessionStatus =
  | "pending"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export type BranchStatus =
  | "pending"
  | "running"
  | "paused"
  | "completed"
  | "pruned"
  | "failed";

export interface ProjectCreate {
  title: string;
  description?: string | null;
  field?: string | null;
  settings?: Record<string, unknown>;
}

export interface Project extends ProjectCreate {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface SessionCreate {
  project_id?: string | null;
  initial_query: string;
  source_providers?: string[];
  filters?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
}

export interface ResearchSession extends SessionCreate {
  project_id: string | null;
  source_providers: string[];
  filters: Record<string, unknown>;
  parameters: Record<string, unknown>;
  id: string;
  status: SessionStatus;
  failure_reason?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Branch {
  id: string;
  session_id: string;
  parent_branch_id?: string | null;
  query: string;
  label?: string | null;
  rationale?: string | null;
  mode: string;
  status: BranchStatus;
  prune_reason?: string | null;
  failure_reason?: string | null;
  depth: number;
  context_tokens_used: number;
  max_context_tokens?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Paper {
  id: string;
  canonical_key: string;
  semantic_scholar_id?: string | null;
  arxiv_id?: string | null;
  doi?: string | null;
  openalex_id?: string | null;
  title: string;
  abstract?: string | null;
  authors: Array<Record<string, unknown>>;
  year?: number | null;
  venue?: string | null;
  citation_count?: number | null;
  reference_count?: number | null;
  influential_citation_count?: number | null;
  url?: string | null;
  pdf_url?: string | null;
  open_access_pdf_url?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SessionPaperView {
  id: string;
  session_id: string;
  branch_id?: string | null;
  paper_id: string;
  discovery_method?: string | null;
  selection_reason?: string | null;
  selected: boolean;
  iteration_number?: number | null;
  paper: Paper;
  created_at: string;
}

export interface Claim {
  id: string;
  session_id: string;
  branch_id?: string | null;
  paper_id?: string | null;
  summary_id?: string | null;
  claim_text: string;
  claim_type: string;
  status: string;
  confidence?: number | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClaimEvidence {
  id: string;
  claim_id: string;
  session_id: string;
  source_type: string;
  paper_id?: string | null;
  chunk_id?: string | null;
  metadata_field?: string | null;
  evidence_text: string;
  relation: string;
  score?: number | null;
  page_start?: number | null;
  page_end?: number | null;
  section_title?: string | null;
  created_at: string;
}

export interface ClaimValidationTrace {
  id: string;
  status: string;
  confidence?: number | null;
  validator_type: string;
  notes?: string | null;
  evidence_ids: string[];
  created_at: string;
}

export interface ClaimInspection {
  claim: Claim;
  evidence: ClaimEvidence[];
  validations: ClaimValidationTrace[];
  paper?: Paper | null;
}

export interface ClaimAutoValidationResult {
  inspection: ClaimInspection;
  candidates_considered: number;
  evidence_retrieved: number;
}

export interface EventRecord {
  id: string;
  session_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  branch_id?: string | null;
  paper_id?: string | null;
  severity: string;
  created_at: string;
}

export interface Job {
  id: string;
  session_id: string;
  branch_id?: string | null;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  priority: number;
  attempts: number;
  max_attempts: number;
  timeout_seconds: number;
  run_at: string;
  locked_by?: string | null;
  locked_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface SessionSnapshot {
  session: ResearchSession;
  runtime_loop?: {
    session_id: string;
    loop_id: string;
    loop_number: number;
    root_branch_id: string;
    created_at: string;
    updated_at: string;
  } | null;
  branches: Branch[];
  jobs: Job[];
  papers: SessionPaperView[];
  summaries: unknown[];
  claims: Claim[];
  claim_evidence: ClaimEvidence[];
  events: EventRecord[];
}

export interface ProjectMetrics {
  sessionCount: number;
  paperCount: number;
  claimCount: number;
  activeSessionCount: number;
  updatedAt: string;
}
