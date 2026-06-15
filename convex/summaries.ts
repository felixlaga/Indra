import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    sessionId: v.id("sessions"),
    branchId: v.string(),
    paperId: v.string(),
    paperTitle: v.string(),
    summary: v.string(),
    groundedness: v.number(),
    iterationNumber: v.number(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("summaries", {
      sessionId: args.sessionId,
      branchId: args.branchId,
      paperId: args.paperId,
      paperTitle: args.paperTitle,
      summary: args.summary,
      groundedness: args.groundedness,
      iterationNumber: args.iterationNumber,
      createdAt: Date.now(),
    });
  },
});

export const createBatch = mutation({
  args: {
    summaries: v.array(
      v.object({
        sessionId: v.id("sessions"),
        branchId: v.string(),
        paperId: v.string(),
        paperTitle: v.string(),
        summary: v.string(),
        groundedness: v.number(),
        iterationNumber: v.number(),
      })
    ),
  },
  handler: async (ctx, args) => {
    const ids = [];
    for (const summary of args.summaries) {
      const id = await ctx.db.insert("summaries", {
        ...summary,
        createdAt: Date.now(),
      });
      ids.push(id);
    }
    return ids;
  },
});

export const getBySession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("summaries")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();
  },
});

export const getByBranch = query({
  args: { branchId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("summaries")
      .withIndex("by_branch", (q) => q.eq("branchId", args.branchId))
      .collect();
  },
});

export const getByPaper = query({
  args: { paperId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("summaries")
      .withIndex("by_paper", (q) => q.eq("paperId", args.paperId))
      .first();
  },
});
