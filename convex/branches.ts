import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    sessionId: v.id("sessions"),
    branchId: v.string(),
    query: v.string(),
    mode: v.string(),
    parentBranchId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("branches", {
      sessionId: args.sessionId,
      branchId: args.branchId,
      query: args.query,
      mode: args.mode as "search_summarize" | "hypothesis",
      status: "pending",
      parentBranchId: args.parentBranchId,
      contextWindowUsed: 0,
      maxContextWindow: 128000,
      paperCount: 0,
      summaryCount: 0,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
  },
});

export const update = mutation({
  args: {
    branchId: v.string(),
    status: v.optional(v.string()),
    contextWindowUsed: v.optional(v.number()),
    paperCount: v.optional(v.number()),
    summaryCount: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const branch = await ctx.db
      .query("branches")
      .withIndex("by_branch_id", (q) => q.eq("branchId", args.branchId))
      .first();
    if (!branch) return null;

    const updates: Record<string, unknown> = { updatedAt: Date.now() };
    if (args.status) updates.status = args.status;
    if (args.contextWindowUsed !== undefined)
      updates.contextWindowUsed = args.contextWindowUsed;
    if (args.paperCount !== undefined) updates.paperCount = args.paperCount;
    if (args.summaryCount !== undefined)
      updates.summaryCount = args.summaryCount;

    await ctx.db.patch(branch._id, updates);
    return branch._id;
  },
});

export const getBySession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("branches")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();
  },
});

export const getTree = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    const branches = await ctx.db
      .query("branches")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();

    const nodes = branches.map((b) => ({
      id: b.branchId,
      query: b.query,
      status: b.status,
      mode: b.mode,
      contextUtilization: b.contextWindowUsed / b.maxContextWindow,
      paperCount: b.paperCount,
      summaryCount: b.summaryCount,
      parentId: b.parentBranchId,
    }));

    const edges = branches
      .filter((b) => b.parentBranchId)
      .map((b) => ({
        source: b.parentBranchId!,
        target: b.branchId,
      }));

    return { nodes, edges };
  },
});
