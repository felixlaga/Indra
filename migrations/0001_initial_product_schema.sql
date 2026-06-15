-- Initial ERLA product schema.
--
-- This migration creates the durable Postgres tables described in DATA_MODEL.md.
-- It does not wire the API skeleton to Postgres or start background jobs.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE,
  name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text,
  field text,
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE research_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid REFERENCES projects(id) ON DELETE CASCADE,
  initial_query text NOT NULL,
  status text NOT NULL CHECK (
    status IN ('pending', 'running', 'paused', 'completed', 'cancelled', 'failed')
  ),
  source_providers text[] NOT NULL DEFAULT '{}'::text[],
  filters jsonb NOT NULL DEFAULT '{}'::jsonb,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE branches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  parent_branch_id uuid REFERENCES branches(id) ON DELETE CASCADE,
  query text NOT NULL,
  label text,
  rationale text,
  mode text NOT NULL CHECK (
    mode IN ('search_summarize', 'hypothesis', 'synthesis', 'gap_analysis')
  ),
  status text NOT NULL CHECK (
    status IN ('pending', 'running', 'paused', 'completed', 'pruned', 'failed')
  ),
  depth integer NOT NULL DEFAULT 0 CHECK (depth >= 0),
  context_tokens_used integer NOT NULL DEFAULT 0 CHECK (context_tokens_used >= 0),
  max_context_tokens integer CHECK (max_context_tokens IS NULL OR max_context_tokens > 0),
  filters jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE papers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_key text UNIQUE,
  semantic_scholar_id text,
  arxiv_id text,
  doi text,
  openalex_id text,
  title text NOT NULL,
  abstract text,
  year integer,
  venue text,
  publication_date date,
  citation_count integer CHECK (citation_count IS NULL OR citation_count >= 0),
  reference_count integer CHECK (reference_count IS NULL OR reference_count >= 0),
  influential_citation_count integer CHECK (
    influential_citation_count IS NULL OR influential_citation_count >= 0
  ),
  url text,
  pdf_url text,
  open_access_pdf_url text,
  external_ids jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE paper_authors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  author_id text,
  name text NOT NULL,
  position integer CHECK (position IS NULL OR position >= 0),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE session_papers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  discovery_method text CHECK (
    discovery_method IS NULL OR discovery_method IN (
      'query_search',
      'citation',
      'reference',
      'user_upload',
      'manual_add',
      'agent_recommendation'
    )
  ),
  selection_reason text,
  selected boolean NOT NULL DEFAULT false,
  iteration_number integer CHECK (iteration_number IS NULL OR iteration_number >= 0),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE paper_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  target_paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  edge_type text NOT NULL CHECK (
    edge_type IN (
      'cites',
      'referenced_by',
      'related',
      'same_author',
      'methodologically_related',
      'contradicts',
      'supports'
    )
  ),
  source_provider text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (source_paper_id <> target_paper_id)
);

CREATE TABLE paper_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  source_type text NOT NULL CHECK (
    source_type IN ('pdf', 'html', 'abstract', 'user_upload')
  ),
  storage_uri text,
  raw_text text,
  parse_status text NOT NULL CHECK (
    parse_status IN ('pending', 'parsed', 'failed', 'unavailable')
  ),
  parser_name text,
  parser_version text,
  page_count integer CHECK (page_count IS NULL OR page_count >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE paper_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES paper_documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL CHECK (chunk_index >= 0),
  text text NOT NULL,
  page_start integer CHECK (page_start IS NULL OR page_start >= 0),
  page_end integer CHECK (page_end IS NULL OR page_end >= 0),
  section_title text,
  token_count integer CHECK (token_count IS NULL OR token_count >= 0),
  embedding vector,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (page_end IS NULL OR page_start IS NULL OR page_end >= page_start)
);

CREATE TABLE summaries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
  paper_id uuid REFERENCES papers(id) ON DELETE SET NULL,
  summary_type text NOT NULL CHECK (
    summary_type IN ('paper', 'branch', 'session', 'field', 'method', 'contradiction', 'gap')
  ),
  text text NOT NULL,
  groundedness_score double precision CHECK (
    groundedness_score IS NULL OR groundedness_score >= 0
  ),
  validation_status text NOT NULL CHECK (
    validation_status IN (
      'not_validated',
      'validated',
      'partially_validated',
      'failed_validation'
    )
  ),
  model text,
  prompt_version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
  paper_id uuid REFERENCES papers(id) ON DELETE SET NULL,
  summary_id uuid REFERENCES summaries(id) ON DELETE SET NULL,
  claim_text text NOT NULL,
  claim_type text NOT NULL CHECK (
    claim_type IN (
      'factual',
      'methodological',
      'empirical_result',
      'theoretical_result',
      'definition',
      'limitation',
      'assumption',
      'comparison',
      'hypothesis',
      'recommendation'
    )
  ),
  status text NOT NULL CHECK (
    status IN (
      'supported',
      'weakly_supported',
      'contradicted',
      'not_found',
      'speculative',
      'needs_review'
    )
  ),
  confidence double precision CHECK (
    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
  ),
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE claim_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  paper_id uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  chunk_id uuid REFERENCES paper_chunks(id) ON DELETE SET NULL,
  evidence_text text NOT NULL,
  relation text NOT NULL CHECK (
    relation IN ('supports', 'weakly_supports', 'contradicts', 'mentions', 'insufficient')
  ),
  score double precision CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
  page_start integer CHECK (page_start IS NULL OR page_start >= 0),
  page_end integer CHECK (page_end IS NULL OR page_end >= 0),
  section_title text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (page_end IS NULL OR page_start IS NULL OR page_end >= page_start)
);

CREATE TABLE validations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type text NOT NULL CHECK (
    target_type IN ('summary', 'claim', 'hypothesis', 'synthesis')
  ),
  target_id uuid NOT NULL,
  validator_type text NOT NULL CHECK (
    validator_type IN ('halugate_token', 'nli', 'claim_evidence', 'manual')
  ),
  status text NOT NULL CHECK (
    status IN ('passed', 'failed', 'partial', 'error', 'not_applicable')
  ),
  score double precision CHECK (score IS NULL OR score >= 0),
  raw_result jsonb NOT NULL DEFAULT '{}'::jsonb,
  model text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE hypotheses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
  text text NOT NULL,
  rationale text,
  confidence double precision CHECK (
    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
  ),
  testability double precision CHECK (
    testability IS NULL OR (testability >= 0 AND testability <= 1)
  ),
  novelty_estimate double precision CHECK (
    novelty_estimate IS NULL OR (novelty_estimate >= 0 AND novelty_estimate <= 1)
  ),
  risk_level text CHECK (
    risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'unknown')
  ),
  status text CHECK (
    status IS NULL OR status IN ('draft', 'supported', 'weak', 'rejected', 'selected', 'archived')
  ),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE hypothesis_support (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hypothesis_id uuid NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
  claim_id uuid REFERENCES claims(id) ON DELETE SET NULL,
  paper_id uuid REFERENCES papers(id) ON DELETE SET NULL,
  relation text NOT NULL CHECK (
    relation IN ('supports', 'motivates', 'contradicts', 'missing_evidence', 'background')
  ),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
  decision_type text NOT NULL CHECK (
    decision_type IN (
      'paper_selection',
      'query_generation',
      'branch_split',
      'branch_prune',
      'branch_continue',
      'hypothesis_generation',
      'gap_detection',
      'reading_plan',
      'research_direction',
      'export_synthesis'
    )
  ),
  input_summary text,
  decision text NOT NULL,
  rationale text,
  alternatives jsonb NOT NULL DEFAULT '[]'::jsonb,
  confidence double precision CHECK (
    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
  ),
  model text,
  prompt_version text,
  token_usage jsonb NOT NULL DEFAULT '{}'::jsonb,
  cost jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
  paper_id uuid REFERENCES papers(id) ON DELETE SET NULL,
  event_type text NOT NULL,
  severity text NOT NULL CHECK (
    severity IN ('debug', 'info', 'warning', 'error', 'critical')
  ),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE exports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  export_type text NOT NULL CHECK (
    export_type IN (
      'markdown_report',
      'latex_outline',
      'bibtex',
      'ris',
      'claim_ledger_csv',
      'claim_ledger_json',
      'research_map_json',
      'annotated_bibliography'
    )
  ),
  status text NOT NULL CHECK (status IN ('pending', 'ready', 'failed')),
  storage_uri text,
  content text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_research_sessions_project_id ON research_sessions(project_id);
CREATE INDEX idx_branches_session_id ON branches(session_id);
CREATE INDEX idx_branches_parent_branch_id ON branches(parent_branch_id);
CREATE INDEX idx_papers_canonical_key ON papers(canonical_key);
CREATE INDEX idx_papers_doi ON papers(doi);
CREATE INDEX idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX idx_papers_semantic_scholar_id ON papers(semantic_scholar_id);
CREATE INDEX idx_session_papers_session_id ON session_papers(session_id);
CREATE INDEX idx_session_papers_branch_id ON session_papers(branch_id);
CREATE INDEX idx_session_papers_paper_id ON session_papers(paper_id);
CREATE INDEX idx_paper_edges_source_paper_id ON paper_edges(source_paper_id);
CREATE INDEX idx_paper_edges_target_paper_id ON paper_edges(target_paper_id);
CREATE INDEX idx_paper_chunks_paper_id ON paper_chunks(paper_id);
CREATE INDEX idx_claims_session_id ON claims(session_id);
CREATE INDEX idx_claims_branch_id ON claims(branch_id);
CREATE INDEX idx_claims_paper_id ON claims(paper_id);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claim_evidence_claim_id ON claim_evidence(claim_id);
CREATE INDEX idx_hypotheses_session_id ON hypotheses(session_id);
CREATE INDEX idx_agent_decisions_session_id ON agent_decisions(session_id);
CREATE INDEX idx_events_session_created_at ON events(session_id, created_at);

CREATE UNIQUE INDEX idx_session_papers_unique_session_paper_branch
ON session_papers(
  session_id,
  paper_id,
  (COALESCE(branch_id, '00000000-0000-0000-0000-000000000000'::uuid))
);

-- A pgvector ANN index should be added once the embedding model and dimension
-- are fixed. The nullable vector column is present so later migrations can add
-- retrieval without altering the paper chunk identity model.

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_research_sessions_updated_at
BEFORE UPDATE ON research_sessions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_branches_updated_at
BEFORE UPDATE ON branches
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_papers_updated_at
BEFORE UPDATE ON papers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_paper_documents_updated_at
BEFORE UPDATE ON paper_documents
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_summaries_updated_at
BEFORE UPDATE ON summaries
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_claims_updated_at
BEFORE UPDATE ON claims
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_hypotheses_updated_at
BEFORE UPDATE ON hypotheses
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_exports_updated_at
BEFORE UPDATE ON exports
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
