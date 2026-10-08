"use client";
import { useEffect, useRef } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";

import { linkStyle, nodeTooltip, type CanvasProps, type GNode, type GLink } from "./shared";

// Labels that stay readable at any zoom; papers only show theirs once zoomed in.
function labelVisible(node: GNode, scale: number): boolean {
  if (node.kind === "branch" || node.kind === "hypothesis") return true;
  if (node.kind === "paper" || node.kind === "contradiction") return scale > 1.4;
  return scale > 2.6;
}

export default function Canvas2D({ data, width, height, selectedId, onSelect }: CanvasProps) {
  const ref = useRef<ForceGraphMethods<GNode, GLink> | undefined>(undefined);
  const fitted = useRef(false);

  useEffect(() => {
    const graph = ref.current;
    if (!graph) return;
    graph.d3Force("charge")?.strength?.(-70);
    const link = graph.d3Force("link");
    link?.distance?.((l: GLink) => linkStyle(l.kind).distance);
    fitted.current = false;
    graph.d3ReheatSimulation();
  }, [data]);

  return (
    <ForceGraph2D<GNode, GLink>
      ref={ref}
      graphData={data}
      width={width}
      height={height}
      backgroundColor="#0a0d12"
      nodeVal={(node) => node.val}
      nodeLabel={(node) => nodeTooltip(node)}
      nodeCanvasObjectMode={() => "replace"}
      nodeCanvasObject={(node, ctx, scale) => {
        const radius = Math.sqrt(node.val) * 4;
        ctx.beginPath();
        ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI);
        ctx.globalAlpha = node.kind === "found" ? 0.75 : 1;
        ctx.fillStyle = node.color;
        ctx.fill();
        ctx.globalAlpha = 1;
        if (node.kind === "hypothesis" || node.root || node.id === selectedId) {
          ctx.lineWidth = (node.id === selectedId ? 3 : 1.5) / scale;
          ctx.strokeStyle = node.id === selectedId ? "#ffffff" : "rgba(255,255,255,0.6)";
          ctx.beginPath();
          ctx.arc(node.x ?? 0, node.y ?? 0, radius + 3 / scale, 0, 2 * Math.PI);
          ctx.stroke();
        }
        if (!labelVisible(node, scale) && node.id !== selectedId) return;
        const size = (node.root ? 14 : 11) / scale;
        ctx.font = `${node.root ? 600 : 400} ${size}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = node.kind === "found" ? "rgba(154,167,183,0.85)" : "#e6ebf1";
        ctx.fillText(node.label, node.x ?? 0, (node.y ?? 0) + radius + 2 / scale);
      }}
      linkColor={(link) => link.color}
      linkWidth={(link) => linkStyle(link.kind).width}
      linkLineDash={(link) => (link.kind === "related" || link.kind === "found" ? [2, 3] : null)}
      linkDirectionalArrowLength={(link) => (link.kind === "cites" ? 4 : 0)}
      linkDirectionalArrowRelPos={0.9}
      linkDirectionalParticles={(link) => linkStyle(link.kind).particles}
      linkDirectionalParticleWidth={2}
      linkDirectionalParticleSpeed={0.006}
      cooldownTicks={180}
      onEngineStop={() => {
        if (fitted.current) return;
        fitted.current = true;
        ref.current?.zoomToFit(500, 50);
      }}
      onNodeClick={(node) => onSelect(node)}
    />
  );
}
