/**
 * Build the session's research graph, after ERLA's: branches, the papers each
 * read or only found, citations between them, and the hypotheses, gaps and
 * contradictions drawn from the checked claims.
 *
 * The map supplies papers and citation edges; the snapshot (branches, claims,
 * evidence) and the advisor output (hypotheses, open problems, contradictions)
 * are optional, so the map page can draw papers alone.
 */

import { evidenceEdges } from "./session-hub.js";

/** @typedef {"branch" | "paper" | "found" | "hypothesis" | "gap" | "contradiction"} GraphNodeKind */
/** @typedef {"split" | "read" | "found" | "cites" | "related" | "evidence" | "supports" | "contradicts" | "gap" | "conflict"} GraphLinkKind */
/**
 * @typedef {{
 *   id: string,
 *   kind: GraphNodeKind,
 *   label: string,
 *   title: string,
 *   color: string,
 *   val: number,
 *   refId: string,
 *   root?: boolean,
 *   detail: Record<string, unknown>,
 * }} GraphNode
 */
/** @typedef {{ source: string, target: string, kind: GraphLinkKind, color: string }} GraphLink */

export const GRAPH_COLORS = {
  root: "#f2f5f8",
  branch: "#6aa9ff",
  running: "#22d3ee",
  paused: "#f3bb63",
  failed: "#ff7b7b",
  unchecked: "#9aa7b7",
  found: "#56667b",
  hypothesis: "#b57bff",
  gap: "#f3bb63",
  contradiction: "#ff5f5f",
  links: {
    split: "#6aa9ff",
    read: "#4fd1a1",
    found: "rgba(111, 124, 140, 0.35)",
    cites: "#8bbcff",
    related: "rgba(154, 167, 183, 0.35)",
    evidence: "#4fd1a1",
    supports: "#f472b6",
    contradicts: "#ff5f5f",
    gap: "#f3bb63",
    conflict: "#ff5f5f",
  },
};

// How far a claim status counts towards a paper being grounded, as in ERLA's groundedness.
const GROUNDING = {
  supported: 1,
  weakly_supported: 0.65,
  not_found: 0.25,
  contradicted: 0,
};
const MAX_GAPS = 30;

/** @param {string} text @param {number} [length] */
export function shorten(text, length = 60) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  return clean.length <= length ? clean : `${clean.slice(0, length - 1)}…`;
}

/** Red → amber → green for grounding 0 → 1. @param {number} value */
export function groundingColor(value) {
  const stops = [
    [255, 95, 95],
    [243, 187, 99],
    [79, 209, 161],
  ];
  const scaled = Math.max(0, Math.min(1, value)) * 2;
  const index = Math.min(1, Math.floor(scaled));
  const t = scaled - index;
  const [a, b] = [stops[index], stops[index + 1]];
  const mix = a.map((channel, i) => Math.round(channel + (b[i] - channel) * t));
  return `rgb(${mix.join(", ")})`;
}

/** @param {Array<{ paper_id?: string | null, status: string }>} claims */
export function paperGrounding(claims) {
  /** @type {Map<string, { checked: number, score: number, total: number }>} */
  const byPaper = new Map();
  for (const claim of claims) {
    if (!claim.paper_id) continue;
    const entry = byPaper.get(claim.paper_id) ?? { checked: 0, score: 0, total: 0 };
    entry.total += 1;
    if (claim.status in GROUNDING) {
      entry.checked += 1;
      entry.score += GROUNDING[/** @type {keyof typeof GROUNDING} */ (claim.status)];
    }
    byPaper.set(claim.paper_id, entry);
  }
  return byPaper;
}

/** @param {number | null | undefined} count */
function citationWeight(count) {
  return Math.log10(1 + Math.max(0, count ?? 0));
}

/** @param {string | undefined} status @param {boolean} root */
function branchColor(status, root) {
  if (status === "running") return GRAPH_COLORS.running;
  if (status === "paused") return GRAPH_COLORS.paused;
  if (status === "failed" || status === "pruned") return GRAPH_COLORS.failed;
  return root ? GRAPH_COLORS.root : GRAPH_COLORS.branch;
}

/**
 * @param {{
 *   map: { nodes: any[], edges: any[], clusters?: any[] },
 *   snapshot?: { session?: { initial_query?: string }, branches: any[], claims: any[], claim_evidence?: any[] } | null,
 *   advice?: { hypotheses?: any[], open_problems?: any[], contradictions?: any[] } | null,
 * }} sources
 * @param {{ found?: boolean, ideas?: boolean, contradictions?: boolean, related?: boolean }} [show]
 * @returns {{ nodes: GraphNode[], links: GraphLink[], counts: Record<string, number> }}
 */
export function buildResearchGraph({ map, snapshot, advice }, show = {}) {
  const options = { found: true, ideas: true, contradictions: true, related: false, ...show };
  /** @type {GraphNode[]} */
  const nodes = [];
  /** @type {GraphLink[]} */
  const links = [];
  const ids = new Set();
  /** @param {GraphNode} node */
  const addNode = (node) => {
    if (ids.has(node.id)) return false;
    ids.add(node.id);
    nodes.push(node);
    return true;
  };
  /** @param {string} source @param {string} target @param {GraphLinkKind} kind */
  const addLink = (source, target, kind) => {
    if (ids.has(source) && ids.has(target) && source !== target)
      links.push({ source, target, kind, color: GRAPH_COLORS.links[kind] });
  };

  // Branches: the session's own when known, else the map's branch clusters.
  const branches = snapshot?.branches?.length
    ? snapshot.branches.map((branch) => ({
        id: branch.id,
        parent: branch.parent_branch_id ?? null,
        label: branch.label || branch.query,
        query: branch.query,
        status: branch.status,
        rationale: branch.rationale,
      }))
    : (map.clusters ?? [])
        .filter((cluster) => cluster.branch_id)
        .map((cluster) => ({
          id: cluster.branch_id,
          parent: null,
          label: cluster.label,
          query: cluster.label,
          status: undefined,
          rationale: null,
        }));
  const readCount = new Map();
  for (const node of map.nodes)
    if (node.read !== false && node.branch_id)
      readCount.set(node.branch_id, (readCount.get(node.branch_id) ?? 0) + 1);
  for (const branch of branches) {
    const root = !branch.parent;
    const label =
      root && snapshot?.session?.initial_query ? snapshot.session.initial_query : branch.label;
    addNode({
      id: `branch:${branch.id}`,
      kind: "branch",
      label: shorten(label, 70),
      title: label,
      color: branchColor(branch.status, root),
      val: (root ? 14 : 8) + Math.min(readCount.get(branch.id) ?? 0, 8),
      refId: branch.id,
      root,
      detail: { query: branch.query, status: branch.status, rationale: branch.rationale },
    });
  }
  for (const branch of branches)
    if (branch.parent) addLink(`branch:${branch.parent}`, `branch:${branch.id}`, "split");

  // Papers: read ones coloured by how their claims held up; found ones dim.
  const grounding = paperGrounding(snapshot?.claims ?? []);
  for (const paper of map.nodes) {
    const read = paper.read !== false;
    if (!read && !options.found) continue;
    const ground = grounding.get(paper.paper_id);
    const checked = ground && ground.checked ? ground.score / ground.checked : null;
    addNode({
      id: `paper:${paper.paper_id}`,
      kind: read ? "paper" : "found",
      label: shorten(paper.title, 60),
      title: paper.title,
      color: !read
        ? GRAPH_COLORS.found
        : checked === null
          ? GRAPH_COLORS.unchecked
          : groundingColor(checked),
      val: read ? 3 + 2 * citationWeight(paper.citation_count) : 1 + citationWeight(paper.citation_count),
      refId: paper.paper_id,
      detail: {
        year: paper.year,
        venue: paper.venue,
        citations: paper.citation_count,
        role: paper.role,
        reason: paper.selection_reason,
        grounding: checked,
        claims: ground?.total ?? 0,
        checkedClaims: ground?.checked ?? 0,
      },
    });
    if (paper.branch_id)
      addLink(`branch:${paper.branch_id}`, `paper:${paper.paper_id}`, read ? "read" : "found");
  }
  for (const edge of map.edges) {
    if (!edge.observed && !options.related) continue;
    addLink(
      `paper:${edge.source_paper_id}`,
      `paper:${edge.target_paper_id}`,
      edge.observed && edge.edge_type === "cites" ? "cites" : "related",
    );
  }

  // A passage in one paper that supports or contradicts a claim from another.
  if (snapshot?.claim_evidence)
    for (const edge of evidenceEdges(/** @type {any} */ (snapshot)))
      addLink(
        `paper:${edge.source_paper_id}`,
        `paper:${edge.target_paper_id}`,
        edge.relation === "contradicts" ? "contradicts" : "evidence",
      );

  const claimPaper = new Map((snapshot?.claims ?? []).map((claim) => [claim.id, claim.paper_id]));
  if (options.ideas) {
    // Hypotheses from the session synthesis connect findings across papers. The
    // advisor's rule-based proposals only restate unchecked claims, so they stay off.
    for (const hypothesis of (advice?.hypotheses ?? []).filter((h) => h.source === "model")) {
      const id = `hypothesis:${hypothesis.id}`;
      addNode({
        id,
        kind: "hypothesis",
        label: shorten(hypothesis.text, 70),
        title: hypothesis.text,
        color: GRAPH_COLORS.hypothesis,
        val: 5 + 4 * (hypothesis.confidence ?? 0),
        refId: hypothesis.id,
        detail: {
          rationale: hypothesis.rationale,
          testability: hypothesis.testability,
          risk: hypothesis.risk,
          source: hypothesis.source,
          nextSteps: hypothesis.next_steps,
        },
      });
      for (const paperId of hypothesis.supporting_paper_ids ?? [])
        addLink(`paper:${paperId}`, id, "supports");
      for (const claimId of hypothesis.contradicting_claim_ids ?? []) {
        const paperId = claimPaper.get(claimId);
        if (paperId) addLink(`paper:${paperId}`, id, "contradicts");
      }
      for (const [index, missing] of (hypothesis.missing_evidence ?? []).entries()) {
        const gapId = `gap:${hypothesis.id}:${index}`;
        addNode({
          id: gapId,
          kind: "gap",
          label: shorten(`Missing: ${missing}`, 70),
          title: missing,
          color: GRAPH_COLORS.gap,
          val: 2.5,
          refId: hypothesis.id,
          detail: { gapKind: "Evidence a hypothesis still needs", hypothesis: hypothesis.text },
        });
        addLink(id, gapId, "gap");
      }
    }
    // Limitations and future work that papers state about their own findings.
    let gaps = 0;
    for (const problem of advice?.open_problems ?? []) {
      const papers = (problem.paper_ids ?? []).filter((/** @type {string} */ paperId) =>
        ids.has(`paper:${paperId}`),
      );
      if (problem.source === "gap_signal" || gaps >= MAX_GAPS || !papers.length) continue;
      const gapId = `gap:${problem.id}`;
      if (
        !addNode({
          id: gapId,
          kind: "gap",
          label: shorten(problem.text, 70),
          title: problem.text,
          color: GRAPH_COLORS.gap,
          val: 2.5,
          refId: problem.id,
          detail: {
            gapKind:
              problem.source === "limitation_claim"
                ? "Limitation stated by a paper"
                : "Future work suggested by a paper",
          },
        })
      )
        continue;
      gaps += 1;
      for (const paperId of papers) addLink(`paper:${paperId}`, gapId, "gap");
    }
  }

  if (options.contradictions) {
    for (const conflict of advice?.contradictions ?? []) {
      const id = `contradiction:${conflict.id}`;
      addNode({
        id,
        kind: "contradiction",
        label: shorten(conflict.description, 70),
        title: conflict.description,
        color: GRAPH_COLORS.contradiction,
        val: conflict.status === "observed" ? 4 : 3,
        refId: conflict.id,
        detail: { rationale: conflict.rationale, status: conflict.status },
      });
      for (const paperId of conflict.paper_ids ?? []) addLink(`paper:${paperId}`, id, "conflict");
    }
  }

  /** @type {Record<string, number>} */
  const counts = {};
  for (const node of nodes) counts[node.kind] = (counts[node.kind] ?? 0) + 1;
  counts.cites = links.filter((link) => link.kind === "cites").length;
  return { nodes, links, counts };
}
