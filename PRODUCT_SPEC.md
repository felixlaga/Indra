# ERLA Product Specification

## 1. Product thesis

ERLA is an epistemic research navigator.

It helps researchers move from an unclear research question to an evidence-backed research map, reading plan, gap analysis, and defensible project direction. Every important claim, summary, hypothesis, and agent decision must be traceable to source material.

The current codebase already contains the seed of this product: recursive Scouts implemented as branches, paper search, summarization, HaluGate validation, branch management, reflection, and hypothesis generation. The product must now move from CLI prototype to online research dashboard.

ERLA should not primarily compete as an AI writing autocomplete tool. Its strongest position is before the writing stage: discovery, mapping, verification, synthesis, and research advising.

## 2. One-line description

ERLA maps a research field, explores literature through autonomous Scouts, validates generated claims against sources, and advises the researcher on what is known, what is uncertain, what to read, and what to investigate next.

## 3. Core promise

Given a research question, ERLA should produce:

1. A live research map.
2. A branch tree showing how the system explored the field.
3. A paper library with validated summaries.
4. A claim ledger where every factual claim links to evidence.
5. A gap and contradiction analysis.
6. A reading plan.
7. Research-direction recommendations.
8. Exportable citations, notes, and review outlines.

## 4. Target users

Primary users:

- Graduate students entering a new field.
- Researchers starting a literature review.
- PhD students looking for thesis directions.
- Academic founders or technical builders exploring research-heavy markets.
- Interdisciplinary researchers crossing into unfamiliar domains.

Secondary users:

- Research labs onboarding students.
- R&D teams scanning academic literature.
- Students preparing theses or grant proposals.

## 5. User problem

Researchers do not only need help writing. They need help deciding:

- What is the field?
- Which papers matter?
- Which papers are foundational?
- Which papers are recent and important?
- What claims are actually supported?
- Where do papers disagree?
- What assumptions keep recurring?
- What methods dominate?
- What open problems remain?
- What should I read first?
- What research direction is realistic and valuable?

Most AI research tools flatten this into chat or generated prose. ERLA should preserve structure, uncertainty, provenance, and exploration history.

## 6. Product principles

### 6.1 Evidence before eloquence

A beautiful answer without source support is a failure.

Every factual claim promoted to the knowledge base must be linked to source evidence. Hypotheses and speculation are allowed only when explicitly labeled as such.

### 6.2 Navigation before writing

ERLA should first help the user understand the landscape. Writing exports come after discovery, mapping, and verification.

### 6.3 Transparency over magic

The user must see:

- What ERLA searched.
- Why a branch was created.
- Why a paper was selected.
- Which source passages support a claim.
- What confidence level was assigned.
- Where evidence is missing or contradictory.

### 6.4 Researcher control

Autonomy is useful only if controllable. Users must be able to pause, resume, redirect, prune, rename, or deepen branches.

### 6.5 Uncertainty is a feature

ERLA should clearly distinguish:

- Supported claims.
- Weakly supported claims.
- Contradicted claims.
- Unverified claims.
- Speculative hypotheses.
- Agent recommendations.

### 6.6 The system is not an author by default

ERLA may draft outlines, notes, annotated bibliographies, and literature review skeletons, but its primary identity is a research navigator and advisor.

## 7. Competitive position

Jenni-style tools are strongest at AI-assisted writing, citation insertion, and sentence-level drafting. ERLA should not initially try to beat them at autocomplete.

ERLA should win by solving the upstream research problem:

- What should I read?
- What does the field look like?
- What claims are supported?
- Where are the gaps?
- What is a promising research direction?

ResearchRabbit and Connected Papers are strong at citation graph exploration. ERLA should combine graph exploration with validated summaries, claim ledgers, hypotheses, contradictions, gap detection, and autonomous Scouts.

Elicit-style tools are strong at structured evidence extraction and review workflows. ERLA should differentiate through live recursive exploration, branch reasoning, visual navigation, and epistemic traceability.

## 8. Core concepts

### 8.1 Project

A long-lived workspace around a broad research area.

A project contains sessions, papers, claims, notes, exports, and preferences.

### 8.2 Research session

A run started from a specific query. A project can contain many sessions.

A session contains:

- Initial query.
- Search filters.
- Source providers.
- Branches.
- Papers discovered.
- Validated summaries.
- Claims.
- Hypotheses.
- Agent decisions.
- Exports.

### 8.3 Scout / branch

A Scout is an autonomous research branch exploring a subquestion, subfield, citation path, time period, method, or hypothesis.

Each branch has:

- Query.
- Parent branch.
- Status.
- Rationale.
- Papers found.
- Summaries.
- Claims.
- Hypotheses.
- Agent decisions.
- Events.

### 8.4 Paper

A normalized academic source from Semantic Scholar, arXiv, future providers, or user upload.

A paper may have:

- Metadata.
- Abstract.
- PDF.
- Full text.
- Chunks.
- References.
- Citations.
- Summaries.
- Claims.
- User notes.

### 8.5 Claim

An atomic factual statement extracted from a paper summary, answer, or synthesis.

Claims must have an evidence status:

- `supported`
- `weakly_supported`
- `contradicted`
- `not_found`
- `speculative`
- `needs_review`

### 8.6 Evidence

A passage, page, section, figure caption, abstract sentence, or metadata field supporting or contradicting a claim.

Evidence must be inspectable in the UI.

### 8.7 Hypothesis

A possible research direction generated from evidence. It is not a validated fact.

A hypothesis must include:

- Text.
- Supporting papers or claims.
- Missing evidence.
- Confidence.
- Testability.
- Risk.
- Next steps.

### 8.8 Agent decision

A stored record explaining why ERLA selected a paper, generated a query, split a branch, pruned a branch, recommended a reading plan, or proposed a hypothesis.

## 9. MVP scope

The first real MVP must include:

1. Web dashboard.
2. Project and session creation.
3. Run control: start, pause, resume, cancel.
4. Branch tree visualization.
5. Paper list.
6. Validated paper summaries.
7. Basic claim extraction.
8. Claim evidence panel.
9. Agent event log.
10. Export to Markdown and BibTeX.

The MVP does not need:

- Full collaborative editing.
- Advanced document writing.
- Mobile layout.
- Payment system.
- Browser extension.
- Institutional admin dashboard.
- Perfect systematic review workflows.

## 10. Product quality bar

A feature is not complete unless:

1. It is visible in the dashboard if user-facing.
2. It stores durable state if it affects a session.
3. It handles errors clearly.
4. It exposes provenance.
5. It has tests.
6. It has a user-facing failure mode.
7. It does not silently hallucinate or overwrite evidence.

## 11. Long-term vision

ERLA becomes a research operating system for navigating knowledge.

A user should be able to say:

> I want to work on this field. Show me the landscape, teach me what matters, find the open problems, and help me choose a serious research direction.

ERLA should respond with a structured, inspectable, evidence-backed research workspace.
