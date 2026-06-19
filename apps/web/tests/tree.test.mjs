import assert from "node:assert/strict";
import test from "node:test";

import { buildBranchTree } from "../lib/tree.js";

test("buildBranchTree nests children below their durable parent", () => {
  const tree = buildBranchTree([
    { id: "root", parent_branch_id: null, depth: 0 },
    { id: "child-b", parent_branch_id: "root", depth: 1 },
    { id: "child-a", parent_branch_id: "root", depth: 1 },
  ]);

  assert.equal(tree.length, 1);
  assert.equal(tree[0].id, "root");
  assert.deepEqual(
    tree[0].children.map((branch) => branch.id),
    ["child-a", "child-b"],
  );
});

test("buildBranchTree keeps orphaned branches visible", () => {
  const tree = buildBranchTree([
    { id: "orphan", parent_branch_id: "missing", depth: 2 },
  ]);

  assert.equal(tree.length, 1);
  assert.equal(tree[0].id, "orphan");
});
