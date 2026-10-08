"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ResearchAdvice } from "@/lib/advice-types";
import { GRAPH_COLORS, buildResearchGraph, groundingColor } from "@/lib/research-graph.js";
import type { ResearchMap, SessionSnapshot } from "@/lib/types";

import { KIND_LABELS, type CanvasProps, type GNode } from "./shared";

// The canvases touch window and WebGL, so they load in the browser only.
const loading = () => <p className="hub-note rg-loading">Drawing the graph…</p>;
const Canvas3D = dynamic<CanvasProps>(() => import("./canvas-3d"), { ssr: false, loading });
const Canvas2D = dynamic<CanvasProps>(() => import("./canvas-2d"), { ssr: false, loading });

type Mode = "3d" | "2d";
type Inspectable = "branch" | "paper" | "hypothesis";
const MODE_KEY = "indra.graph.mode";

const LEGEND: { label: string; color: string; ring?: boolean; idea?: boolean }[] = [
  { label: "Question", color: GRAPH_COLORS.root, ring: true },
  { label: "Branch", color: GRAPH_COLORS.branch },
  { label: "Paper read (claims held up → contradicted)", color: groundingColor(1) },
  { label: "Paper read, claims not yet verified", color: GRAPH_COLORS.unchecked },
  { label: "Paper found, not read", color: GRAPH_COLORS.found },
  { label: "Hypothesis", color: GRAPH_COLORS.hypothesis, ring: true, idea: true },
  { label: "Gap: missing evidence, limitation, future work", color: GRAPH_COLORS.gap, idea: true },
  { label: "Contradiction", color: GRAPH_COLORS.contradiction, idea: true },
];

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(320, Math.floor(entry.contentRect.width))),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

function NodeDetail({
  node,
  onInspect,
  close,
}: {
  node: GNode;
  onInspect?: (kind: Inspectable, id: string) => void;
  close: () => void;
}) {
  const d = node.detail as Record<string, string | number | null | undefined | string[]>;
  const inspectable = node.kind === "branch" || node.kind === "paper" || node.kind === "hypothesis";
  const facts = [
    d.year && `${d.year}`,
    d.venue && `${d.venue}`,
    typeof d.citations === "number" && `${d.citations} citations`,
    node.kind === "paper" &&
      (d.checkedClaims
        ? `${d.checkedClaims} of ${d.claims} claims verified, ${Math.round(Number(d.grounding) * 100)}% held up`
        : `${d.claims ?? 0} claims, none verified yet`),
    node.kind === "hypothesis" && typeof d.testability === "number" && `testability ${Math.round(d.testability * 100)}%`,
    node.kind === "hypothesis" && d.risk && `risk ${d.risk}`,
  ].filter(Boolean);
  return (
    <aside className="rg-detail" aria-live="polite">
      <header>
        <span className="rg-dot" style={{ background: node.color }} />
        <strong>{node.root ? "Research question" : KIND_LABELS[node.kind]}</strong>
        <button className="hub-text-button" onClick={close} aria-label="Close details">
          ×
        </button>
      </header>
      <p className="rg-detail-title">{node.title}</p>
      {!!facts.length && <p className="rg-detail-facts">{facts.join(" · ")}</p>}
      {typeof d.gapKind === "string" && <p>{d.gapKind}</p>}
      {typeof d.hypothesis === "string" && <p>For: {d.hypothesis}</p>}
      {typeof d.reason === "string" && <p>{d.reason}</p>}
      {typeof d.rationale === "string" && <p>{d.rationale}</p>}
      <div className="rg-detail-actions">
        {(node.kind === "paper" || node.kind === "found") && (
          <Link className="button button-small button-secondary" href={`/papers/${node.refId}`}>
            Open paper
          </Link>
        )}
        {inspectable && onInspect && (
          <button
            className="button button-small button-secondary"
            onClick={() => onInspect(node.kind as Inspectable, node.refId)}
          >
            Inspect
          </button>
        )}
      </div>
    </aside>
  );
}

export function ResearchGraph({
  map,
  snapshot,
  advice,
  onInspect,
}: {
  map: ResearchMap;
  snapshot?: SessionSnapshot | null;
  advice?: ResearchAdvice | null;
  onInspect?: (kind: Inspectable, id: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("3d");
  const [show, setShow] = useState({ found: true, ideas: true, contradictions: true, related: false });
  const [selected, setSelected] = useState<GNode | null>(null);
  const [containerRef, width] = useWidth();
  const height = width < 640 ? 480 : 640;

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(MODE_KEY);
      if (saved === "2d" || saved === "3d") setMode(saved);
    } catch {
      // Storage can be unavailable; the default view still works.
    }
  }, []);
  function changeMode(next: Mode) {
    setMode(next);
    try {
      window.localStorage.setItem(MODE_KEY, next);
    } catch {
      // Not remembered this time.
    }
  }

  // Rebuilt when the view changes too: the force engines write positions into these objects.
  const graph = useMemo(
    () => buildResearchGraph({ map, snapshot, advice }, show),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [map, snapshot, advice, show, mode],
  );
  const { counts } = graph;
  const read = counts.paper ?? 0;
  const found = map.nodes.filter((node) => node.read === false).length;
  // Without advisor output (the map page), only papers and citations are drawn.
  const ideas = advice !== undefined;
  const toggles: [keyof typeof show, string][] = [
    ["found", `Papers found, not read (${found})`],
    ...(ideas
      ? ([
          ["ideas", "Hypotheses and gaps"],
          ["contradictions", "Contradictions"],
        ] as [keyof typeof show, string][])
      : []),
    ["related", "Inferred similarity links"],
  ];

  return (
    <div className="rg">
      <div className="rg-controls">
        <div className="rg-mode" role="group" aria-label="Graph view">
          {(["3d", "2d"] as Mode[]).map((value) => (
            <button
              key={value}
              className={`button button-small ${mode === value ? "button-primary" : "button-secondary"}`}
              aria-pressed={mode === value}
              onClick={() => changeMode(value)}
            >
              {value.toUpperCase()}
            </button>
          ))}
        </div>
        {toggles.map(([key, label]) => (
          <label key={key}>
            <input
              type="checkbox"
              checked={show[key]}
              onChange={(event) => setShow((current) => ({ ...current, [key]: event.target.checked }))}
            />{" "}
            {label}
          </label>
        ))}
      </div>
      <p className="hub-note rg-summary">
        {read} papers read and {found} found but not read · {counts.branch ?? 0} branches ·{" "}
        {ideas &&
          `${
            counts.hypothesis
              ? `${counts.hypothesis} hypotheses`
              : "no hypotheses yet (the model's session synthesis writes them)"
          } · ${counts.gap ?? 0} gaps · ${counts.contradiction ?? 0} contradictions · `}
        {counts.cites} citation links.{" "}
        {mode === "3d" ? "Drag to rotate, scroll to zoom." : "Drag to pan, scroll to zoom."} Click a node for
        details.
      </p>
      <div className="rg-stage" ref={containerRef} aria-label="Research graph">
        {graph.nodes.length === 0 ? (
          <p className="hub-note">No papers to draw yet.</p>
        ) : mode === "3d" ? (
          <Canvas3D
            data={graph}
            width={width}
            height={height}
            selectedId={selected?.id ?? null}
            onSelect={setSelected}
          />
        ) : (
          <Canvas2D
            data={graph}
            width={width}
            height={height}
            selectedId={selected?.id ?? null}
            onSelect={setSelected}
          />
        )}
        {selected && (
          <NodeDetail node={selected} onInspect={onInspect} close={() => setSelected(null)} />
        )}
      </div>
      <ul className="rg-legend">
        {LEGEND.filter((item) => ideas || !item.idea).map((item) => (
          <li key={item.label}>
            <span
              className={`rg-dot${item.ring ? " rg-ring" : ""}`}
              style={{
                background: item.label.startsWith("Paper read (")
                  ? `linear-gradient(90deg, ${groundingColor(1)}, ${groundingColor(0.5)}, ${groundingColor(0)})`
                  : item.color,
              }}
            />
            {item.label}
          </li>
        ))}
        <li>Moving dots follow citations, Scout splits and hypothesis support.</li>
      </ul>
    </div>
  );
}
