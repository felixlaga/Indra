┌─────────────────────────────────────────────────────────────┐
│                        RLM Pipeline                          │
├─────────────────────────────────────────────────────────────┤
│  [User Query: "transformer attention mechanisms"]            │
│                          ↓                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  BASE_LOOP(n=3)                                      │    │
│  │  ┌──────────────────────────────────────────────┐   │    │
│  │  │ 1. Semantic Scholar search(query)            │   │    │
│  │  │ 2. Fetch top-k papers (abstract + refs)      │   │    │
│  │  │ 3. Summarize → HaluGate verify               │   │    │
│  │  │ 4. Extract concepts → new queries            │   │    │
│  │  └──────────────────────────────────────────────┘   │    │
│  │  Output: [verified_summaries], [seed_hypotheses]    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  SHOULDER_BUILD(p=2)                                 │    │
│  │  for hypothesis in seed_hypotheses:                  │    │
│  │      base_loop(hypothesis, n=2)                      │    │
│  │      → cross_pollinate(results)                      │    │
│  │      → generate_novel_hypotheses()                   │    │
│  │  [RECURSIVE if p > 1]                                │    │
│  └──────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│  Output: ranked hypotheses by (novelty × groundedness)       │
└─────────────────────────────────────────────────────────────┘
