# Research graph

The session hub's **Research Graph** tab draws a session the way ERLA's viewer did: a force-directed graph of the question, its branches, the papers they read and the ideas that came out of them. It runs in 3D (ERLA's look, rotate and zoom) or in 2D (labelled, pan and zoom), and the choice is remembered per browser.

## What is drawn

| Node | Shown as | Linked to |
| --- | --- | --- |
| Research question | white, ringed | its Scout branches (moving dots show the split) |
| Scout branch | blue; cyan with a halo while running | the papers it read and found |
| Paper read | red → amber → green by how its verified claims held up (supported, weakly supported, not found, contradicted); grey until a claim is verified; size by citations | papers it cites (arrows, moving dots); papers whose claims its passages support or contradict |
| Paper found, not read | dim slate, small | the branch that found it; citations |
| Hypothesis (from the session synthesis) | purple, ringed | supporting papers (pink) and papers with contradicting claims (red) |
| Gap | amber | a hypothesis's missing evidence, or the paper that states a limitation or suggests future work |
| Contradiction | red | the papers involved |

Clicking a node opens a detail card with the paper's year, venue, citations, claim verdicts and why it was read or only found. "Inspect" opens branches, papers read and hypotheses in the session inspector, and "Open paper" opens any paper's page. Filters hide found papers, hypotheses and gaps, or contradictions, and can add the session-local similarity links.

The advisor's rule-based proposals restate unchecked claims, so they are not drawn as hypotheses. Hypotheses appear once the model has written the session synthesis.

## Many more papers

A branch reads a few papers but searches a larger pool ([paper selection](PAPER_SELECTION.md)). Its on-topic candidates that were not read, up to 60 per branch, are now kept as *found* papers: linked to the session with `selected = false` and a reason such as "Found by the branch's search; the model chose other papers to read". Their OpenAlex citations are looked up with the papers read, so the graph shows citation paths across the whole pool.

Found papers are only for the map. Session paper lists, claims, verification, exports and Scout de-duplication use the papers read, exactly as before. `list_discovered_papers` returns found papers once each, leaving out any paper read elsewhere in the session. The map builder adds them as nodes with `read: false`. The map overview counts them separately (`discovered_paper_count`), and the map cache version is 3, so older cached maps are rebuilt.

The research map page uses the same graph with papers and citations only.

## Expanding the network

**Expand network** in the Research Graph tab adds 50, 100 or 200 papers to a running or completed session (`POST /sessions/{id}/expand` with `{"papers": 100}`; one expansion at a time per session). It queues a `network_expansion` job (migration 0006) that the research worker runs without model calls:

1. **Backward.** It counts the works that the session's papers cite, read and found alike, and fetches the most-cited ones from OpenAlex. These are the shared foundations.
2. **Forward.** It fetches works citing the session's papers twice: once sorted by citations (influential follow-ups) and once by publication date (the frontier).
3. **Deeper search.** It runs the session's own search queries for up to 50 more results each.

Candidates are ranked by relevance to the question (topic words plus embedding similarity, as in [paper selection](PAPER_SELECTION.md)) and by how many session papers they cite or are cited by. Off-topic candidates are dropped unless at least three session papers cite them. The best ones are kept as found papers with `discovery_method` `reference`, `citation` or `query_search` and a reason such as "Cited by 7 papers in this session". The job records a decision summarising what it added.

An expansion runs beside research and never decides when a session finishes. Research jobs ignore it when deciding to queue the synthesis or complete the session, and it may run after the session has completed.

On the gravitational-wave lensing session, one 100-paper expansion grew the network from 28 to 128 papers and from 30 to 2,011 citation links.

## Field insight

The map builder reads structure from the citation network, and the graph shows it below the canvas:

- **Themes.** Louvain modularity communities (seeded, so they repeat) over citation links, with at least 3 papers each. Each theme is named by the words much more common in it than across the network, and gets a year range, a share of recent papers and a key paper. A theme is *emerging* when at least half its papers are from the last three years.
- **Foundations.** The papers cited most often by other papers in the network.
- **Frontier.** The newest papers, ranked by how many network papers they build on.
- **Papers per year** across the whole network.

Nodes are sized partly by in-network citations, and the graph can be coloured by claim verification, citation theme or publication year. The map cache version is 4.

All of this describes the retrieved network, not the whole field.
