# ERLA UI/UX Specification

## 1. UI goal

The ERLA interface should feel like research mission control.

The user should not interact through a CLI. The user should see a complete online dashboard where research exploration is visible, controllable, and inspectable.

The interface must make ERLA's thinking legible without exposing hidden chain-of-thought. Show decisions, rationales, evidence, uncertainty, and progress.

## 2. Core UX principles

### 2.1 The map is central

The main object is not a chat thread. The main object is a research map.

### 2.2 Every generated statement is inspectable

If ERLA says something factual, the user must be able to click into the source evidence.

### 2.3 Autonomy must be controllable

The user must be able to pause, redirect, split, prune, or deepen branches.

### 2.4 Fast perception matters

Even if research jobs take time, the UI must update quickly with incremental progress.

### 2.5 Do not overload the user

The system may generate many papers, claims, and branches. The UI must organize them into clear layers.

## 3. Primary pages

### 3.1 Projects page

Route:

```txt
/projects
```

Purpose:

Show all research projects.

Required elements:

- Project cards.
- Create project button.
- Search/filter projects.
- Last updated timestamp.
- Number of sessions.
- Number of saved papers.
- Number of claims.

### 3.2 Project page

Route:

```txt
/projects/[projectId]
```

Purpose:

Show one long-lived research workspace.

Required elements:

- Project title and description.
- Start new session input.
- Recent sessions.
- Saved papers.
- Saved hypotheses.
- Exports.
- Project settings.

### 3.3 Session dashboard

Route:

```txt
/sessions/[sessionId]
```

Purpose:

Main research mission-control interface.

Layout:

```txt
Top bar:
  session title
  status
  run controls
  export button

Left sidebar:
  query
  filters
  branch list
  source providers
  session stats

Center:
  Scout tree / citation graph / timeline tabs

Right inspector:
  selected node details

Bottom drawer:
  event log
  validation trace
  job status
```

### 3.4 Paper page

Route:

```txt
/papers/[paperId]
```

Purpose:

Inspect a paper.

Required elements:

- Metadata.
- Abstract.
- PDF/full-text status.
- Summary.
- Claims extracted from this paper.
- Evidence passages.
- Citation/reference links.
- Sessions where paper appeared.
- User notes.

### 3.5 Settings page

Route:

```txt
/settings
```

Purpose:

Configure model providers, search providers, validation settings, export settings, and user preferences.

## 4. Session dashboard details

### 4.1 Top bar

Must show:

- Session query.
- Status: pending, running, paused, completed, failed, cancelled.
- Elapsed time.
- Paper count.
- Claim count.
- Branch count.
- Validation progress.

Controls:

- Start.
- Pause.
- Resume.
- Cancel.
- Export.
- Settings.

### 4.2 Left sidebar

Sections:

- Query.
- Filters.
- Branch list.
- Source providers.
- Run settings.

Branch actions:

- Continue.
- Go deeper.
- Split.
- Rename.
- Prune.
- Open details.

### 4.3 Center view

The center view has tabs.

#### Scout Tree

Shows autonomous research branches.

Node types:

- Root query.
- Branch.
- Paper cluster.
- Hypothesis.
- Gap.

#### Citation Graph

Shows papers and citation/reference edges.

Node types:

- Paper.
- Review paper.
- Foundational paper.
- Recent paper.
- User-selected paper.

Edge types:

- Cites.
- Referenced by.
- Supports.
- Contradicts.
- Related.

#### Timeline

Shows papers over time.

Useful for identifying:

- Foundational works.
- Periods of rapid growth.
- Recent developments.
- Method shifts.

#### Claim Map

Shows claims grouped by topic, support level, and contradiction.

## 5. Right inspector

The right inspector changes based on selected object.

### 5.1 Branch inspector

Show:

- Query.
- Rationale.
- Parent branch.
- Status.
- Papers found.
- Summaries validated.
- Claims extracted.
- Agent decisions.
- Suggested next actions.

### 5.2 Paper inspector

Show:

- Title.
- Authors.
- Year.
- Venue.
- Abstract.
- Citation count.
- PDF status.
- Summary.
- Claims.
- Related papers.
- Open paper link.

### 5.3 Claim inspector

Show:

- Claim text.
- Status.
- Confidence.
- Source paper.
- Supporting evidence.
- Contradicting evidence.
- Validation result.
- Related claims.

### 5.4 Hypothesis inspector

Show:

- Hypothesis text.
- Rationale.
- Supporting claims.
- Missing evidence.
- Confidence.
- Testability.
- Risk.
- Suggested next steps.

## 6. Bottom drawer

Tabs:

### Event log

Chronological stream of system events.

### Validation trace

Show validation jobs and outcomes.

### Jobs

Show background jobs:

- Queued.
- Running.
- Completed.
- Failed.
- Retrying.

## 7. Visual design direction

ERLA should look serious, technical, and calm.

Avoid:

- Toy-like AI chatbot aesthetics.
- Excessive gradients.
- Overcrowded neon visuals.
- Pure 3D gimmicks that reduce usability.
- Tiny unreadable graph nodes.

Prefer:

- Dark/light mode support.
- Clean cards.
- Dense but readable data layout.
- Strong typography.
- Subtle status colors.
- Clear hierarchy.
- Fast graph interactions.
- Keyboard shortcuts.

## 8. Required components

Core components:

```txt
ProjectCard
SessionCard
RunControlBar
BranchList
BranchNode
ScoutTree
CitationGraph
TimelineView
ClaimLedger
ClaimStatusBadge
PaperCard
PaperInspector
BranchInspector
ClaimInspector
HypothesisInspector
EventLog
ValidationTrace
JobStatusPanel
ExportDialog
SettingsPanel
```

## 9. Claim ledger UX

The claim ledger is one of ERLA's most important differentiators.

Columns:

- Claim.
- Status.
- Confidence.
- Source paper.
- Evidence count.
- Contradiction count.
- Branch.
- Created at.

Filters:

- Status.
- Paper.
- Branch.
- Claim type.
- Confidence.
- Reviewed/unreviewed.

Clicking a claim opens evidence.

## 10. MVP UI scope

The first frontend MVP must implement:

- Projects page.
- Project page.
- Session dashboard.
- Run control bar.
- Branch tree.
- Paper list.
- Paper inspector.
- Claim ledger.
- Claim inspector.
- Event log.
- Export dialog.

Do not build a full writing editor in the MVP.

## 11. UI performance rules

- Virtualize long lists.
- Paginate papers and claims.
- Do not render thousands of graph nodes at once.
- Use incremental graph loading.
- Debounce search/filter inputs.
- Keep dashboard interactions under 100 ms where possible.
- Use skeleton loading instead of blocking screens.
