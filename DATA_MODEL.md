# ERLA Data Model

## 1. Goal

The data model must support durable, inspectable, evidence-backed research sessions.

The current code uses dataclasses such as `Branch`, `LoopState`, `IterationResult`, `ValidatedSummary`, and `ResearchHypothesis`. Those are useful runtime objects, but production needs durable database entities.

Use Postgres as the source of truth. Use pgvector when embedding-based retrieval is added.

## 2. Core entities

Required product entities:

- User.
- Project.
- ResearchSession.
- Branch.
- Paper.
- PaperAuthor.
- SessionPaper.
- PaperEdge.
- PaperDocument.
- PaperChunk.
- Summary.
- Claim.
- ClaimEvidence.
- Validation.
- Hypothesis.
- HypothesisSupport.
- AgentDecision.
- Event.
- Export.

## 3. Naming rules

Use snake_case database names.

Use UUID primary keys.

Keep external IDs separate from internal IDs.

Every table should have:

```txt
id uuid primary key
created_at timestamptz
updated_at timestamptz where updates are expected
```

## 4. Tables

### 4.1 users

```txt
id uuid primary key
email text unique
name text
created_at timestamptz
updated_at timestamptz
```

### 4.2 projects

```txt
id uuid primary key
user_id uuid references users(id)
title text not null
description text
field text
settings jsonb
created_at timestamptz
updated_at timestamptz
```

### 4.3 research_sessions

```txt
id uuid primary key
project_id uuid references projects(id)
initial_query text not null
status text not null
source_providers text[]
filters jsonb
parameters jsonb
started_at timestamptz
completed_at timestamptz
created_at timestamptz
updated_at timestamptz
```

Allowed statuses:

```txt
pending
running
paused
completed
cancelled
failed
```

### 4.4 branches

Maps to the current runtime concept in `src/orchestration/models.py`.

```txt
id uuid primary key
session_id uuid references research_sessions(id)
parent_branch_id uuid references branches(id)
query text not null
label text
rationale text
mode text not null
status text not null
depth integer default 0
context_tokens_used integer default 0
max_context_tokens integer
filters jsonb
created_at timestamptz
updated_at timestamptz
```

Allowed modes:

```txt
search_summarize
hypothesis
synthesis
gap_analysis
```

Allowed statuses:

```txt
pending
running
paused
completed
pruned
failed
```

### 4.5 papers

Normalized academic papers. Current `PaperDetails` fields should map into this table.

```txt
id uuid primary key
canonical_key text unique
semantic_scholar_id text
arxiv_id text
doi text
openalex_id text
title text not null
abstract text
year integer
venue text
publication_date date
citation_count integer
reference_count integer
influential_citation_count integer
url text
pdf_url text
open_access_pdf_url text
external_ids jsonb
metadata jsonb
created_at timestamptz
updated_at timestamptz
```

Canonical key priority:

1. DOI.
2. arXiv ID.
3. Semantic Scholar ID.
4. OpenAlex ID.
5. normalized title + year fallback.

### 4.6 paper_authors

```txt
id uuid primary key
paper_id uuid references papers(id)
author_id text
name text not null
position integer
metadata jsonb
created_at timestamptz
```

### 4.7 session_papers

Join table between sessions, branches, and papers.

```txt
id uuid primary key
session_id uuid references research_sessions(id)
branch_id uuid references branches(id)
paper_id uuid references papers(id)
discovery_method text
selection_reason text
selected boolean default false
iteration_number integer
created_at timestamptz
```

Discovery methods:

```txt
query_search
citation
reference
user_upload
manual_add
agent_recommendation
```

### 4.8 paper_edges

Citation/reference graph.

```txt
id uuid primary key
source_paper_id uuid references papers(id)
target_paper_id uuid references papers(id)
edge_type text not null
source_provider text
created_at timestamptz
```

Allowed edge types:

```txt
cites
referenced_by
related
same_author
methodologically_related
contradicts
supports
```

For citation edges:

- `source_paper_id` = citing paper.
- `target_paper_id` = cited paper.

### 4.9 paper_documents

```txt
id uuid primary key
paper_id uuid references papers(id)
source_type text not null
storage_uri text
raw_text text
parse_status text
parser_name text
parser_version text
page_count integer
created_at timestamptz
updated_at timestamptz
```

Source types:

```txt
pdf
html
abstract
user_upload
```

Parse statuses:

```txt
pending
parsed
failed
unavailable
```

### 4.10 paper_chunks

```txt
id uuid primary key
paper_id uuid references papers(id)
document_id uuid references paper_documents(id)
chunk_index integer not null
text text not null
page_start integer
page_end integer
section_title text
token_count integer
embedding vector
metadata jsonb
created_at timestamptz
```

### 4.11 summaries

Maps to current `ValidatedSummary`, but must support versioning and validation state.

```txt
id uuid primary key
session_id uuid references research_sessions(id)
branch_id uuid references branches(id)
paper_id uuid references papers(id)
summary_type text not null
text text not null
groundedness_score double precision
validation_status text
model text
prompt_version text
created_at timestamptz
updated_at timestamptz
```

Summary types:

```txt
paper
branch
session
field
method
contradiction
gap
```

Validation statuses:

```txt
not_validated
validated
partially_validated
failed_validation
```

### 4.12 claims

Atomic factual or speculative claims.

```txt
id uuid primary key
session_id uuid references research_sessions(id)
branch_id uuid references branches(id)
paper_id uuid references papers(id)
summary_id uuid references summaries(id)
claim_text text not null
claim_type text not null
status text not null
confidence double precision
created_by text
created_at timestamptz
updated_at timestamptz
```

Claim types:

```txt
factual
methodological
empirical_result
theoretical_result
definition
limitation
assumption
comparison
hypothesis
recommendation
```

Claim statuses:

```txt
supported
weakly_supported
contradicted
not_found
speculative
needs_review
```

### 4.13 claim_evidence

```txt
id uuid primary key
claim_id uuid references claims(id)
paper_id uuid references papers(id)
chunk_id uuid references paper_chunks(id)
evidence_text text not null
relation text not null
score double precision
page_start integer
page_end integer
section_title text
created_at timestamptz
```

Relations:

```txt
supports
weakly_supports
contradicts
mentions
insufficient
```

### 4.14 validations

```txt
id uuid primary key
target_type text not null
target_id uuid not null
validator_type text not null
status text not null
score double precision
raw_result jsonb
model text
created_at timestamptz
```

Target types:

```txt
summary
claim
hypothesis
synthesis
```

Validator types:

```txt
halugate_token
nli
claim_evidence
manual
```

Statuses:

```txt
passed
failed
partial
error
not_applicable
```

### 4.15 hypotheses

Maps to current `ResearchHypothesis`, extended for product use.

```txt
id uuid primary key
session_id uuid references research_sessions(id)
branch_id uuid references branches(id)
text text not null
rationale text
confidence double precision
testability double precision
novelty_estimate double precision
risk_level text
status text
created_at timestamptz
updated_at timestamptz
```

Risk levels:

```txt
low
medium
high
unknown
```

Statuses:

```txt
draft
supported
weak
rejected
selected
archived
```

### 4.16 hypothesis_support

```txt
id uuid primary key
hypothesis_id uuid references hypotheses(id)
claim_id uuid references claims(id)
paper_id uuid references papers(id)
relation text not null
created_at timestamptz
```

Relations:

```txt
supports
motivates
contradicts
missing_evidence
background
```

### 4.17 agent_decisions

Audit log for consequential agent decisions.

```txt
id uuid primary key
session_id uuid references research_sessions(id)
branch_id uuid references branches(id)
decision_type text not null
input_summary text
decision text not null
rationale text
alternatives jsonb
confidence double precision
model text
prompt_version text
token_usage jsonb
cost jsonb
created_at timestamptz
```

Decision types:

```txt
paper_selection
query_generation
branch_split
branch_prune
branch_continue
hypothesis_generation
gap_detection
reading_plan
research_direction
export_synthesis
```

### 4.18 events

Realtime and historical event log.

```txt
id uuid primary key
session_id uuid references research_sessions(id)
branch_id uuid references branches(id)
paper_id uuid references papers(id)
event_type text not null
severity text not null
payload jsonb
created_at timestamptz
```

Severities:

```txt
debug
info
warning
error
critical
```

### 4.19 exports

```txt
id uuid primary key
session_id uuid references research_sessions(id)
export_type text not null
status text not null
storage_uri text
content text
metadata jsonb
created_at timestamptz
updated_at timestamptz
```

Export types:

```txt
markdown_report
latex_outline
bibtex
ris
claim_ledger_csv
claim_ledger_json
research_map_json
annotated_bibliography
```

Statuses:

```txt
pending
ready
failed
```

## 5. Indexes

Create indexes for:

```txt
research_sessions(project_id)
branches(session_id)
branches(parent_branch_id)
papers(canonical_key)
papers(doi)
papers(arxiv_id)
papers(semantic_scholar_id)
session_papers(session_id)
session_papers(branch_id)
session_papers(paper_id)
paper_edges(source_paper_id)
paper_edges(target_paper_id)
paper_chunks(paper_id)
claims(session_id)
claims(branch_id)
claims(paper_id)
claims(status)
claim_evidence(claim_id)
hypotheses(session_id)
agent_decisions(session_id)
events(session_id, created_at)
```

For pgvector:

```txt
paper_chunks.embedding vector index
```

The initial schema migration creates the nullable `paper_chunks.embedding` vector column. Add the ANN vector index in a later migration once the embedding model and vector dimension are chosen.

## 6. State reconstruction

The dashboard must be reconstructable from durable tables, not only realtime events.

To render a session:

1. Load session.
2. Load branches.
3. Load session papers.
4. Load paper edges.
5. Load summaries.
6. Load claims and evidence.
7. Load hypotheses.
8. Load recent events.

Events are for replay and live updates. Tables are the source of truth.

## 7. Data quality rules

- Do not create duplicate papers if DOI/arXiv/Semantic Scholar ID matches.
- Do not promote claims without validation status.
- Do not delete failed jobs; store failure state.
- Do not overwrite agent decisions.
- Do not overwrite summaries without versioning.
- Do not store secret keys.
- Do not treat citation count as quality by itself.
