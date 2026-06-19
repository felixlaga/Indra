export function layoutResearchMap(nodes, clusters, width = 1040, height = 560) {
  const paddingX = 76;
  const paddingY = 66;
  const knownYears = nodes.map((node) => node.year).filter((year) => Number.isFinite(year));
  const minYear = knownYears.length ? Math.min(...knownYears) : 0;
  const maxYear = knownYears.length ? Math.max(...knownYears) : minYear;
  const yearSpan = Math.max(1, maxYear - minYear);
  const clusterOrder = new Map(clusters.map((cluster, index) => [cluster.id, index]));
  const clusterCount = Math.max(1, clusters.length);
  const buckets = new Map();

  return nodes.map((node) => {
    const clusterIndex = clusterOrder.get(node.cluster_id) ?? clusterCount - 1;
    const yearRatio = Number.isFinite(node.year) ? (node.year - minYear) / yearSpan : 0.5;
    const key = String(node.cluster_id) + ":" + String(node.year ?? "unknown");
    const bucketIndex = buckets.get(key) ?? 0;
    buckets.set(key, bucketIndex + 1);
    const jitterX = ((bucketIndex % 3) - 1) * 18;
    const jitterY = Math.floor(bucketIndex / 3) * 18;
    const x = paddingX + yearRatio * (width - paddingX * 2) + jitterX;
    const laneHeight = (height - paddingY * 2) / clusterCount;
    const y = paddingY + laneHeight * (clusterIndex + 0.5) + jitterY;
    const radius = Math.max(7, Math.min(18, 7 + Math.log1p(node.citation_count ?? 0) * 1.7));
    return { ...node, x, y, radius };
  });
}

export function edgeCoordinates(edge, positionedNodes) {
  const byId = new Map(positionedNodes.map((node) => [node.paper_id, node]));
  const source = byId.get(edge.source_paper_id);
  const target = byId.get(edge.target_paper_id);
  if (!source || !target) return null;
  return { x1: source.x, y1: source.y, x2: target.x, y2: target.y };
}
