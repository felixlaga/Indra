# Agent Architecture: Simple Agents, Emergent Behavior

## Core Philosophy
Simple autonomous agents with clear responsibilities combine to create intelligent research behavior.

---

## Three Simple Agents

```
┌─────────────────────────────────────────────────────────────┐
│                     MASTER AGENT                             │
│                                                              │
│  Simple Rules:                                               │
│  • If context > 80% full → split branch                     │
│  • If papers ≥ 15 → enable hypothesis mode                  │
│  • Else → continue iterations                               │
│                                                              │
│  Emergent Behavior: Exponential exploration                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   ITERATION AGENT                            │
│                                                              │
│  Simple Rules:                                               │
│  • Iteration 1 → search with query                          │
│  • Iteration 2+ → follow paper citations                    │
│                                                              │
│  Emergent Behavior: Deep citation graph traversal           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SEARCH AGENT                              │
│                                                              │
│  Simple Loop:                                                │
│    Search → Summarize → Validate → Retry if needed          │
│                                                              │
│  Emergent Behavior: High-quality knowledge extraction       │
└─────────────────────────────────────────────────────────────┘
```

---

## The Core Loop: Search → Summarize → Validate

```
           ┌──────────────────────────────────────┐
           │      Find papers                     │
           │      (Semantic Scholar)              │
           └───────────┬──────────────────────────┘
                       │
                       ▼
           ┌──────────────────────────────────────┐
           │      Generate summary                │
           │      (LLM)                           │
           └───────────┬──────────────────────────┘
                       │
                       ▼
           ┌──────────────────────────────────────┐
           │      Validate groundedness           │
           │      (HaluGate ≥ 95%)               │
           └───────────┬──────────────────────────┘
                       │
                 ┌─────┴─────┐
                 │           │
              PASS          FAIL
                 │           │
                 │           ▼
                 │    ┌──────────────────┐
                 │    │  Retry with      │
                 │    │  strict guidance │
                 │    └────────┬─────────┘
                 │             │
                 └─────┬───────┘
                       │
                       ▼
                   [Accept]
```

---

## How Emergence Happens

### Simple Rule: "Split when context full"
```
Branch A (80% full)
    │
    ├──▶ Branch A1 (topic 1)
    │
    ├──▶ Branch A2 (topic 2)
    │
    └──▶ Branch A3 (topic 3)

Result: Parallel exploration of diverse topics
```

### Simple Rule: "Follow citations"
```
Iteration 1: Find 5 papers
               │
Iteration 2: Find 20 papers citing those
               │
Iteration 3: Find 80+ papers citing those

Result: Exponential knowledge graph expansion
```

### Simple Rule: "Validate everything"
```
100 papers found
    │
    ├──▶ 85 pass validation (≥95%)
    │
    └──▶ 15 retried → 12 pass with guidance

Result: High-quality, trustworthy summaries
```

---

## Two Modes, One System

```
MODE 1: Exploration          MODE 2: Hypothesis Generation
┌──────────────────┐        ┌──────────────────────────┐
│                  │        │                          │
│  Search papers   │        │  Search papers           │
│       ↓          │        │       ↓                  │
│  Summarize       │───────▶│  Summarize               │
│       ↓          │        │       ↓                  │
│  Validate        │        │  Validate                │
│                  │        │       ↓                  │
│                  │        │  Find patterns           │
│                  │        │       ↓                  │
│                  │        │  Generate questions      │
│                  │        │                          │
└──────────────────┘        └──────────────────────────┘
   (Default)                  (After 15+ papers)
```

---

## The Result: Intelligent Research from Simple Rules

```
Simple Agents          →          Emergent Behavior
─────────────                     ──────────────────

Split when full        →          Parallel exploration
Follow citations       →          Deep graph traversal
Validate summaries     →          Trusted knowledge
Enable hypotheses      →          Novel insights
Retry on failure       →          Robust quality
```

---

## File References

- **Master Agent**: `src/orchestration/master_agent.py`
- **Iteration Agent**: `src/orchestration/iteration_loop.py`
- **Search Agent**: `src/orchestration/inner_loop.py`
- **Validator**: `src/orchestration/overseer.py`
- **Hypothesis Generator**: `src/hypothesis/generator.py`
