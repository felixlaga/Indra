import type { ResearchMapCluster, ResearchMapEdge, ResearchMapNode } from "@/lib/types";

export type PositionedResearchMapNode = ResearchMapNode & { x: number; y: number; radius: number };

export function layoutResearchMap(nodes: ResearchMapNode[], clusters: ResearchMapCluster[], width?: number, height?: number): PositionedResearchMapNode[];

export function edgeCoordinates(edge: ResearchMapEdge, positionedNodes: PositionedResearchMapNode[]): { x1: number; y1: number; x2: number; y2: number } | null;
