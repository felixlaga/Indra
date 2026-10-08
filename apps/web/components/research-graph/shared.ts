import type { GraphLink, GraphLinkKind, GraphNode } from "@/lib/research-graph.js";

export type GNode = GraphNode & { x?: number; y?: number; z?: number };
export type GLink = Omit<GraphLink, "source" | "target"> & {
  source: string | GNode;
  target: string | GNode;
};

export interface CanvasProps {
  data: { nodes: GNode[]; links: GLink[] };
  width: number;
  height: number;
  selectedId: string | null;
  onSelect: (node: GNode) => void;
}

const STYLES: Record<GraphLinkKind, { width: number; particles: number; distance: number }> = {
  split: { width: 2.5, particles: 2, distance: 90 },
  read: { width: 1.4, particles: 0, distance: 55 },
  found: { width: 0.5, particles: 0, distance: 70 },
  cites: { width: 0.9, particles: 1, distance: 45 },
  related: { width: 0.6, particles: 0, distance: 60 },
  evidence: { width: 1.4, particles: 1, distance: 55 },
  supports: { width: 1.6, particles: 2, distance: 60 },
  contradicts: { width: 1.6, particles: 2, distance: 60 },
  gap: { width: 1.1, particles: 0, distance: 35 },
  conflict: { width: 1.6, particles: 1, distance: 45 },
};

export function linkStyle(kind: GraphLinkKind) {
  return STYLES[kind];
}

export const KIND_LABELS: Record<GraphNode["kind"], string> = {
  branch: "Branch",
  paper: "Paper read",
  found: "Paper found, not read",
  hypothesis: "Hypothesis",
  gap: "Gap",
  contradiction: "Contradiction",
};

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/** Hover card; paper titles come from external sources, so everything is escaped. */
export function nodeTooltip(node: GNode): string {
  const kind = node.root ? "Research question" : KIND_LABELS[node.kind];
  const year = node.detail.year ? ` · ${escapeHtml(String(node.detail.year))}` : "";
  return `<div class="rg-tooltip"><strong style="color:${node.color}">${kind}${year}</strong><span>${escapeHtml(node.title)}</span></div>`;
}
