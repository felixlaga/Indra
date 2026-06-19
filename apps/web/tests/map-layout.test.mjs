import assert from "node:assert/strict";
import test from "node:test";

import { edgeCoordinates, layoutResearchMap } from "../lib/map-layout.js";

const clusters = [
  { id: "cluster-a", label: "A", paper_ids: ["a", "b"] },
  { id: "cluster-b", label: "B", paper_ids: ["c"] },
];
const nodes = [
  { paper_id: "a", cluster_id: "cluster-a", year: 2010, citation_count: 100 },
  { paper_id: "b", cluster_id: "cluster-a", year: 2020, citation_count: 3 },
  { paper_id: "c", cluster_id: "cluster-b", year: 2025, citation_count: 0 },
];

test("layout places later papers farther right", () => {
  const positioned = layoutResearchMap(nodes, clusters, 1000, 500);
  const byId = new Map(positioned.map((node) => [node.paper_id, node]));
  assert.ok(byId.get("a").x < byId.get("b").x);
  assert.ok(byId.get("b").x < byId.get("c").x);
});

test("layout separates cluster lanes and scales citation radius", () => {
  const positioned = layoutResearchMap(nodes, clusters, 1000, 500);
  const byId = new Map(positioned.map((node) => [node.paper_id, node]));
  assert.notEqual(byId.get("a").y, byId.get("c").y);
  assert.ok(byId.get("a").radius > byId.get("b").radius);
});

test("edge coordinates resolve only when both nodes exist", () => {
  const positioned = layoutResearchMap(nodes, clusters);
  assert.ok(edgeCoordinates({ source_paper_id: "a", target_paper_id: "c" }, positioned));
  assert.equal(
    edgeCoordinates({ source_paper_id: "a", target_paper_id: "missing" }, positioned),
    null,
  );
});
