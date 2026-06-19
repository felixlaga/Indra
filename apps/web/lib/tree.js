/**
 * @typedef {{ id: string, parent_branch_id?: string | null, depth?: number }} BranchLike
 * @typedef {BranchLike & { children: BranchTreeNode[] }} BranchTreeNode
 */

/**
 * Build a stable branch forest. Orphaned branches are intentionally promoted to
 * roots so incomplete durable state remains visible instead of disappearing.
 *
 * @template {BranchLike} T
 * @param {T[]} branches
 * @returns {Array<T & { children: BranchTreeNode[] }>}
 */
export function buildBranchTree(branches) {
  /** @type {Map<string, T & { children: BranchTreeNode[] }>} */
  const nodes = new Map(
    branches.map((branch) => [branch.id, { ...branch, children: [] }]),
  );
  /** @type {Array<T & { children: BranchTreeNode[] }>} */
  const roots = [];

  for (const branch of branches) {
    const node = nodes.get(branch.id);
    if (!node) continue;
    const parentId = branch.parent_branch_id;
    const parent = parentId ? nodes.get(parentId) : undefined;
    if (parent && parent.id !== node.id) {
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }

  /** @param {BranchTreeNode[]} items */
  const sortNodes = (items) => {
    items.sort((left, right) => {
      const depthDelta = (left.depth ?? 0) - (right.depth ?? 0);
      return depthDelta || left.id.localeCompare(right.id);
    });
    for (const item of items) sortNodes(item.children);
  };
  sortNodes(roots);
  return roots;
}
