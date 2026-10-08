"use client";
import { useEffect, useRef } from "react";
import ForceGraph3D, { type ForceGraphMethods } from "react-force-graph-3d";
import * as THREE from "three";

import { linkStyle, nodeTooltip, type CanvasProps, type GNode, type GLink } from "./shared";

// ERLA's look: the question and hypotheses carry a ring, running branches glow.
function decoration(node: GNode): THREE.Object3D | null {
  const radius = Math.cbrt(node.val) * 4;
  if (node.kind === "hypothesis" || node.root) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius + (node.root ? 4 : 2), node.root ? 0.7 : 0.4, 8, 48),
      new THREE.MeshBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.5 }),
    );
    ring.rotation.x = Math.PI / 2;
    return ring;
  }
  if (node.kind === "branch" && node.detail.status === "running") {
    // depthWrite off keeps the halo from hiding the branch inside it.
    return new THREE.Mesh(
      new THREE.SphereGeometry(radius + 3, 24, 24),
      new THREE.MeshBasicMaterial({
        color: node.color,
        transparent: true,
        opacity: 0.18,
        depthWrite: false,
      }),
    );
  }
  return null;
}

export default function Canvas3D({ data, width, height, onSelect }: CanvasProps) {
  const ref = useRef<ForceGraphMethods<GNode, GLink> | undefined>(undefined);
  const fitted = useRef(false);
  const shown = useRef(0);

  useEffect(() => {
    const graph = ref.current;
    if (!graph) return;
    graph.d3Force("charge")?.strength?.(-90);
    graph.d3Force("link")?.distance?.((l: GLink) => linkStyle(l.kind).distance);
    // Re-fit the view when papers are added, not when the same graph refreshes.
    if (data.nodes.length !== shown.current) {
      shown.current = data.nodes.length;
      fitted.current = false;
    }
    graph.d3ReheatSimulation();
  }, [data]);

  return (
    <ForceGraph3D<GNode, GLink>
      ref={ref}
      graphData={data}
      width={width}
      height={height}
      backgroundColor="#0a0d12"
      nodeVal={(node) => node.val}
      nodeColor={(node) => node.color}
      nodeOpacity={0.92}
      nodeResolution={16}
      nodeLabel={(node) => nodeTooltip(node)}
      nodeThreeObjectExtend
      nodeThreeObject={(node) => decoration(node) ?? new THREE.Object3D()}
      linkColor={(link) => link.color}
      linkWidth={(link) => (link.kind === "split" ? 1.2 : 0)}
      linkOpacity={0.45}
      linkDirectionalParticles={(link) => linkStyle(link.kind).particles}
      linkDirectionalParticleWidth={1.6}
      linkDirectionalParticleSpeed={0.006}
      cooldownTicks={200}
      onEngineStop={() => {
        if (fitted.current) return;
        fitted.current = true;
        ref.current?.zoomToFit(600, 40);
      }}
      onNodeClick={(node) => {
        onSelect(node);
        const { x = 0, y = 0, z = 0 } = node;
        const ratio = 1 + 120 / Math.max(1, Math.hypot(x, y, z));
        ref.current?.cameraPosition({ x: x * ratio, y: y * ratio, z: z * ratio }, { x, y, z }, 900);
      }}
    />
  );
}
