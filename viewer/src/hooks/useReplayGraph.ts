import { useMemo } from "react";

interface NodeData {
  id: string;
  type: string;
  label: string;
  color: string;
  size: number;
  data: Record<string, unknown>;
}

interface LinkData {
  source: string;
  target: string;
  type: string;
}

interface GraphData {
  nodes: NodeData[];
  links: LinkData[];
  stats: {
    branchCount: number;
    paperCount: number;
    summaryCount: number;
    hypothesisCount: number;
  };
}

interface UseReplayGraphResult {
  filteredGraph: GraphData;
  visibleNodeIds: Set<string>;
  visibleLinkIds: Set<string>;
}

/**
 * Hook to filter graph data based on replay time.
 * Shows only nodes/links that existed at the given time.
 * Uses the createdAt timestamp from each node's data.
 */
export function useReplayGraph(
  fullGraph: GraphData | undefined,
  _events: unknown[] | undefined, // Kept for API compatibility
  currentTime: number
): UseReplayGraphResult {
  return useMemo(() => {
    if (!fullGraph) {
      return {
        filteredGraph: {
          nodes: [],
          links: [],
          stats: { branchCount: 0, paperCount: 0, summaryCount: 0, hypothesisCount: 0 },
        },
        visibleNodeIds: new Set(),
        visibleLinkIds: new Set(),
      };
    }

    // Filter nodes based on their createdAt timestamp
    const visibleNodes = fullGraph.nodes.filter((node) => {
      const createdAt = node.data.createdAt as number | undefined;
      // If no createdAt, include the node (backwards compatibility)
      if (createdAt === undefined) {
        return true;
      }
      return createdAt <= currentTime;
    });

    const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));

    // Filter links - both source and target must be visible
    const visibleLinks = fullGraph.links.filter((link) => {
      const sourceId = typeof link.source === "string" ? link.source : (link.source as NodeData).id;
      const targetId = typeof link.target === "string" ? link.target : (link.target as NodeData).id;
      return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId);
    });

    const visibleLinkIds = new Set(
      visibleLinks.map((l) => {
        const sourceId = typeof l.source === "string" ? l.source : (l.source as NodeData).id;
        const targetId = typeof l.target === "string" ? l.target : (l.target as NodeData).id;
        return `${sourceId}-${targetId}`;
      })
    );

    // Calculate filtered stats
    const stats = {
      branchCount: visibleNodes.filter((n) => n.type === "branch").length,
      paperCount: visibleNodes.filter((n) => n.type === "paper").length,
      summaryCount: visibleNodes.filter((n) => n.type === "paper" && n.data.summaryText).length,
      hypothesisCount: visibleNodes.filter((n) => n.type === "hypothesis").length,
    };

    return {
      filteredGraph: {
        nodes: visibleNodes,
        links: visibleLinks,
        stats,
      },
      visibleNodeIds,
      visibleLinkIds,
    };
  }, [fullGraph, currentTime]);
}
