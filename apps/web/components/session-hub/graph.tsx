"use client";
import { useMemo, useRef, useState } from "react";
import { evidenceEdges, graphPositions } from "@/lib/session-hub.js";
import type { ResearchMap, SessionSnapshot } from "@/lib/types";

export function CitationGraph({
  map,
  snapshot,
  select,
  selectedId,
}: {
  map: ResearchMap;
  snapshot: SessionSnapshot;
  select: (type: string, id: string) => void;
  selectedId: string | null;
}) {
  const layout = useMemo(() => graphPositions(map.nodes), [map.nodes]);
  const nodes = new Map(layout.nodes.map((node) => [node.paper_id, node]));
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [related, setRelated] = useState(false);
  const drag = useRef<{
    x: number;
    y: number;
    px: number;
    py: number;
    scale: number;
  } | null>(null);
  const edges = map.edges.filter((edge) => edge.observed || related);
  const relations = evidenceEdges(snapshot).filter(
    (edge) =>
      nodes.has(edge.source_paper_id) && nodes.has(edge.target_paper_id),
  );
  const move = (x: number, y: number) =>
    setPan((p) => ({ x: p.x + x, y: p.y + y }));
  return (
    <div className="hub-graph">
      <div className="hub-graph-controls">
        <button
          className="button button-small button-secondary"
          aria-label="Zoom out"
          disabled={zoom <= 0.5}
          onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
        >
          −
        </button>
        <output aria-label="Graph zoom">{Math.round(zoom * 100)}%</output>
        <button
          className="button button-small button-secondary"
          aria-label="Zoom in"
          disabled={zoom >= 3}
          onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
        >
          +
        </button>
        <button
          className="button button-small button-secondary"
          onClick={() => {
            setPan({ x: 0, y: 0 });
            setZoom(1);
          }}
        >
          Reset view
        </button>
        <label>
          <input
            type="checkbox"
            checked={related}
            onChange={(event) => setRelated(event.target.checked)}
          />{" "}
          Show inferred links
        </label>
      </div>
      <p className="hub-note">
        Drag the canvas to pan. Focus it and use arrow keys to pan, +/− to zoom.
        Node size reflects citation count, not research quality.
      </p>
      {layout.nodes.length === 0 ? (
        <p className="hub-note">No papers to map yet.</p>
      ) : (
        <svg
          className="hub-graph-canvas"
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="group"
          tabIndex={0}
          aria-label="Interactive citation graph"
          onKeyDown={(event) => {
            if (event.target !== event.currentTarget) return;
            const moves: Record<string, [number, number]> = {
              ArrowLeft: [30, 0],
              ArrowRight: [-30, 0],
              ArrowUp: [0, 30],
              ArrowDown: [0, -30],
            };
            if (moves[event.key]) {
              event.preventDefault();
              move(...moves[event.key]);
            } else if (event.key === "+" || event.key === "=")
              setZoom((z) => Math.min(3, z + 0.25));
            else if (event.key === "-") setZoom((z) => Math.max(0.5, z - 0.25));
          }}
          onPointerDown={(event) => {
            if ((event.target as Element).closest("[data-paper]")) return;
            const scale =
              layout.width / event.currentTarget.getBoundingClientRect().width;
            drag.current = {
              x: event.clientX,
              y: event.clientY,
              px: pan.x,
              py: pan.y,
              scale,
            };
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (drag.current)
              setPan({
                x:
                  drag.current.px +
                  (event.clientX - drag.current.x) * drag.current.scale,
                y:
                  drag.current.py +
                  (event.clientY - drag.current.y) * drag.current.scale,
              });
          }}
          onPointerUp={() => {
            drag.current = null;
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
        >
          <defs>
            <marker
              id="hub-citation-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="8"
              refY="4"
              orient="auto"
            >
              <path d="M0,0 L8,4 L0,8" fill="var(--accent)" />
            </marker>
          </defs>
          <g
            transform={`translate(${pan.x} ${pan.y}) translate(${layout.width / 2} ${layout.height / 2}) scale(${zoom}) translate(${-layout.width / 2} ${-layout.height / 2})`}
          >
            {edges.map((edge) => {
              const a = nodes.get(edge.source_paper_id),
                b = nodes.get(edge.target_paper_id);
              return a && b ? (
                <line
                  key={edge.id}
                  x1={a.x}
                  y1={a.y}
                  x2={
                    b.x -
                    ((b.x - a.x) / (Math.hypot(b.x - a.x, b.y - a.y) || 1)) *
                      (b.radius + 4)
                  }
                  y2={
                    b.y -
                    ((b.y - a.y) / (Math.hypot(b.x - a.x, b.y - a.y) || 1)) *
                      (b.radius + 4)
                  }
                  className={
                    edge.observed ? "hub-edge-cites" : "hub-edge-related"
                  }
                  markerEnd={
                    edge.observed ? "url(#hub-citation-arrow)" : undefined
                  }
                >
                  <title>{edge.provenance}</title>
                </line>
              ) : null;
            })}
            {relations.map((edge) => {
              const a = nodes.get(edge.source_paper_id)!,
                b = nodes.get(edge.target_paper_id)!;
              return (
                <path
                  key={edge.id}
                  d={`M${a.x},${a.y} Q${(a.x + b.x) / 2},${Math.min(a.y, b.y) - (edge.relation === "contradicts" ? 95 : edge.relation === "weakly_supports" ? 65 : 35)} ${b.x},${b.y}`}
                  className={`hub-edge-${edge.relation}`}
                >
                  <title>
                    Source passage {edge.relation.replaceAll("_", " ")} a claim
                    in the target paper; inspect relations below.
                  </title>
                </path>
              );
            })}
            {layout.nodes.map((node, index) => (
              <g
                key={node.paper_id}
                data-paper={node.paper_id}
                role="button"
                tabIndex={0}
                aria-label={`Inspect ${node.title}`}
                aria-pressed={selectedId === node.paper_id}
                transform={`translate(${node.x} ${node.y})`}
                className={`hub-graph-node${selectedId === node.paper_id ? " is-selected" : ""}`}
                onClick={() => select("paper", node.paper_id)}
                onKeyDown={(event) => {
                  if (["Enter", " "].includes(event.key)) {
                    event.preventDefault();
                    select("paper", node.paper_id);
                  }
                }}
              >
                <circle r={node.radius} />
                <text y={4} textAnchor="middle" className="hub-node-number">
                  {index + 1}
                </text>
                <text y={node.radius + 20} textAnchor="middle">
                  {node.title.length > 25
                    ? node.title.slice(0, 24) + "…"
                    : node.title}
                </text>
                <text
                  className="hub-node-year"
                  y={node.radius + 37}
                  textAnchor="middle"
                >
                  {node.year ?? "Undated"}
                </text>
                <title>{node.title}</title>
              </g>
            ))}
          </g>
        </svg>
      )}
      <div className="hub-graph-legend">
        <span className="citation">→ Observed citations</span>
        <span className="support">— Supports</span>
        <span className="contradiction">— Contradicts</span>
        <span>┄ Inferred relatedness</span>
      </div>
      {!map.edges.some((edge) => edge.observed) && (
        <p className="hub-note">
          No observed citation paths are available for these papers. Inferred
          links are hidden by default.
        </p>
      )}
      <details className="hub-list-details">
        <summary>Accessible paper list ({layout.nodes.length})</summary>
        {layout.nodes.map((node, index) => (
          <button
            className="hub-list-button"
            key={node.paper_id}
            onClick={() => select("paper", node.paper_id)}
          >
            {index + 1}. {node.title} · {node.year ?? "Undated"}
          </button>
        ))}
      </details>
      {relations.length > 0 && (
        <details className="hub-list-details">
          <summary>Evidence relations ({relations.length})</summary>
          <p className="hub-note">
            Relations describe specific claims, not agreement between entire
            papers.
          </p>
          {relations.map((edge) => (
            <div key={edge.id} className="hub-relation">
              <p>
                {nodes.get(edge.source_paper_id)?.title} →{" "}
                {nodes.get(edge.target_paper_id)?.title}:{" "}
                {edge.relation.replaceAll("_", " ")}
              </p>
              {edge.claimIds.map((id: string) => (
                <button
                  className="hub-text-button"
                  key={id}
                  onClick={() => select("claim", id)}
                >
                  Inspect claim evidence
                </button>
              ))}
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
