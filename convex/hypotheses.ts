import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    sessionId: v.id("sessions"),
    branchId: v.string(),
    hypothesisId: v.string(),
    text: v.string(),
    supportingPaperIds: v.array(v.string()),
    confidence: v.number(),
    iterationNumber: v.number(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("hypotheses", {
      sessionId: args.sessionId,
      branchId: args.branchId,
      hypothesisId: args.hypothesisId,
      text: args.text,
      supportingPaperIds: args.supportingPaperIds,
      confidence: args.confidence,
      iterationNumber: args.iterationNumber,
      createdAt: Date.now(),
    });
  },
});

export const createBatch = mutation({
  args: {
    hypotheses: v.array(
      v.object({
        sessionId: v.id("sessions"),
        branchId: v.string(),
        hypothesisId: v.string(),
        text: v.string(),
        supportingPaperIds: v.array(v.string()),
        confidence: v.number(),
        iterationNumber: v.number(),
      })
    ),
  },
  handler: async (ctx, args) => {
    const ids = [];
    for (const hypothesis of args.hypotheses) {
      const id = await ctx.db.insert("hypotheses", {
        ...hypothesis,
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
      .query("hypotheses")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();
  },
});

export const getByBranch = query({
  args: { branchId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("hypotheses")
      .withIndex("by_branch", (q) => q.eq("branchId", args.branchId))
      .collect();
  },
});

export const getTopByConfidence = query({
  args: {
    sessionId: v.id("sessions"),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 10;
    const hypotheses = await ctx.db
      .query("hypotheses")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();

    return hypotheses
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, limit);
  },
});
