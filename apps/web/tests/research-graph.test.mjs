import test from "node:test";
import assert from "node:assert/strict";
import {
  GRAPH_COLORS,
  buildResearchGraph,
  groundingColor,
} from "../lib/research-graph.js";

const map = {
  nodes: [
    { paper_id: "p1", title: "Lensed waves", branch_id: "root", citation_count: 40, read: true },
    { paper_id: "p2", title: "Wave optics", branch_id: "scout", citation_count: 3, read: true },
    { paper_id: "p3", title: "Found only", branch_id: "root", citation_count: 9, read: false },
  ],
  edges: [
    { source_paper_id: "p3", target_paper_id: "p1", edge_type: "cites", observed: true },
    { source_paper_id: "p1", target_paper_id: "p2", edge_type: "related", observed: false },
  ],
  clusters: [
    { id: "cluster-root", label: "Lensing", branch_id: "root" },
    { id: "cluster-scout", label: "Wave optics", branch_id: "scout" },
  ],
};
const snapshot = {
  session: { initial_query: "Where is gravitational-wave lensing headed?" },
  branches: [
    { id: "root", parent_branch_id: null, query: "gw lensing", status: "completed" },
    { id: "scout", parent_branch_id: "root", query: "wave optics", label: "Wave optics", status: "running" },
  ],
  claims: [
    { id: "c1", paper_id: "p1", status: "supported" },
    { id: "c2", paper_id: "p2", status: "contradicted" },
    { id: "c3", paper_id: "p2", status: "needs_review" },
  ],
  claim_evidence: [{ claim_id: "c1", paper_id: "p2", relation: "contradicts" }],
};
const advice = {
  hypotheses: [
    {
      id: "h1",
      text: "Microlensing reveals subhalos",
      source: "model",
      confidence: 0.5,
      supporting_paper_ids: ["p1"],
      contradicting_claim_ids: ["c2"],
      missing_evidence: ["A detected wave-optics event"],
    },
    { id: "h2", text: "Rule-based restatement", source: "heuristic", supporting_paper_ids: ["p1"], missing_evidence: [] },
  ],
  open_problems: [
    { id: "o1", text: "Lens models are degenerate", source: "limitation_claim", paper_ids: ["p2"] },
    { id: "o2", text: "Not on the graph", source: "limitation_claim", paper_ids: ["missing"] },
    { id: "o3", text: "Processing signal", source: "gap_signal", paper_ids: ["p1"] },
  ],
  contradictions: [{ id: "x1", description: "Rates disagree", status: "observed", paper_ids: ["p1", "p2"] }],
};

/** @param {{ links: any[] }} graph @param {string} kind */
const pairs = (graph, kind) =>
  graph.links.filter((link) => link.kind === kind).map((link) => `${link.source}>${link.target}`);

test("the graph joins branches, papers read and found, hypotheses, gaps and contradictions", () => {
  const graph = buildResearchGraph({ map, snapshot, advice });
  assert.deepEqual(graph.counts, {
    branch: 2,
    paper: 2,
    found: 1,
    hypothesis: 1,
    gap: 2,
    contradiction: 1,
    cites: 1,
  });
  const root = graph.nodes.find((node) => node.id === "branch:root");
  assert.equal(root.root, true);
  assert.equal(root.label, "Where is gravitational-wave lensing headed?");
  assert.deepEqual(pairs(graph, "split"), ["branch:root>branch:scout"]);
  assert.deepEqual(pairs(graph, "found"), ["branch:root>paper:p3"]);
  assert.deepEqual(pairs(graph, "cites"), ["paper:p3>paper:p1"]);
  assert.deepEqual(pairs(graph, "contradicts"), [
    "paper:p2>paper:p1",
    "paper:p2>hypothesis:h1",
  ]);
  assert.deepEqual(pairs(graph, "supports"), ["paper:p1>hypothesis:h1"]);
  // Missing evidence hangs off its hypothesis; stated limitations off their paper.
  assert.deepEqual(pairs(graph, "gap"), ["hypothesis:h1>gap:h1:0", "paper:p2>gap:o1"]);
  assert.deepEqual(pairs(graph, "conflict"), [
    "paper:p1>contradiction:x1",
    "paper:p2>contradiction:x1",
  ]);
});

test("papers are coloured by how their checked claims held up", () => {
  const graph = buildResearchGraph({ map, snapshot, advice });
  const color = (/** @type {string} */ id) => graph.nodes.find((node) => node.id === id).color;
  assert.equal(color("paper:p1"), groundingColor(1));
  assert.equal(color("paper:p2"), groundingColor(0));
  assert.equal(color("paper:p3"), GRAPH_COLORS.found);
  const unchecked = buildResearchGraph({ map, snapshot: { ...snapshot, claims: [] } });
  assert.equal(unchecked.nodes.find((node) => node.id === "paper:p1").color, GRAPH_COLORS.unchecked);
});

test("filters hide found papers, ideas and contradictions and add inferred links", () => {
  const graph = buildResearchGraph(
    { map, snapshot, advice },
    { found: false, ideas: false, contradictions: false, related: true },
  );
  assert.deepEqual(
    graph.nodes.map((node) => node.kind).sort(),
    ["branch", "branch", "paper", "paper"],
  );
  assert.deepEqual(pairs(graph, "related"), ["paper:p1>paper:p2"]);
});

test("without a snapshot the map's branch clusters become the branches", () => {
  const graph = buildResearchGraph({ map });
  assert.deepEqual(
    graph.nodes.filter((node) => node.kind === "branch").map((node) => node.label),
    ["Lensing", "Wave optics"],
  );
  assert.deepEqual(pairs(graph, "read"), ["branch:root>paper:p1", "branch:scout>paper:p2"]);
});

test("rule-based advisor proposals are not drawn as hypotheses", () => {
  const heuristicOnly = { ...advice, hypotheses: [advice.hypotheses[1]] };
  const graph = buildResearchGraph({ map, snapshot, advice: heuristicOnly });
  assert.equal(graph.counts.hypothesis, undefined);
  // Gaps stated by papers still appear.
  assert.deepEqual(pairs(graph, "gap"), ["paper:p2>gap:o1"]);
});

test("papers can be coloured by citation theme or publication year", async () => {
  const { THEME_COLORS, yearColor } = await import("../lib/research-graph.js");
  const themed = {
    ...map,
    nodes: map.nodes.map((node, i) => ({ ...node, theme_id: i < 2 ? "theme-1" : null, year: 2000 + i * 10 })),
    insight: { themes: [{ id: "theme-1", label: "Lensing" }] },
  };
  const byTheme = buildResearchGraph({ map: themed, snapshot }, { colorBy: "theme" });
  const color = (graph, id) => graph.nodes.find((node) => node.id === id).color;
  assert.equal(color(byTheme, "paper:p1"), THEME_COLORS[0]);
  assert.equal(color(byTheme, "paper:p3"), GRAPH_COLORS.found);
  assert.equal(byTheme.nodes.find((node) => node.id === "paper:p1").detail.theme, "Lensing");
  const byYear = buildResearchGraph({ map: themed, snapshot }, { colorBy: "year" });
  assert.equal(color(byYear, "paper:p1"), yearColor(2000, 2000, 2020));
  assert.equal(color(byYear, "paper:p3"), yearColor(2020, 2000, 2020));
  assert.notEqual(color(byYear, "paper:p1"), color(byYear, "paper:p3"));
});
