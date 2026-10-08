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
