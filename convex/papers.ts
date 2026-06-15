import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    sessionId: v.id("sessions"),
    branchId: v.string(),
    paperId: v.string(),
    title: v.optional(v.string()),
    abstract: v.optional(v.string()),
    authors: v.array(
      v.object({
        authorId: v.optional(v.string()),
        name: v.optional(v.string()),
      })
    ),
    year: v.optional(v.number()),
    citationCount: v.optional(v.number()),
    venue: v.optional(v.string()),
    iterationNumber: v.number(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("papers", {
      sessionId: args.sessionId,
      branchId: args.branchId,
      paperId: args.paperId,
      title: args.title,
      abstract: args.abstract,
      authors: args.authors,
      year: args.year,
      citationCount: args.citationCount,
      venue: args.venue,
      iterationNumber: args.iterationNumber,
      createdAt: Date.now(),
    });
  },
});

export const createBatch = mutation({
  args: {
    papers: v.array(
      v.object({
        sessionId: v.id("sessions"),
        branchId: v.string(),
        paperId: v.string(),
        title: v.optional(v.string()),
        abstract: v.optional(v.string()),
        authors: v.array(
          v.object({
            authorId: v.optional(v.string()),
            name: v.optional(v.string()),
          })
        ),
        year: v.optional(v.number()),
        citationCount: v.optional(v.number()),
        venue: v.optional(v.string()),
        iterationNumber: v.number(),
      })
    ),
  },
  handler: async (ctx, args) => {
    const ids = [];
    for (const paper of args.papers) {
      const id = await ctx.db.insert("papers", {
        ...paper,
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
      .query("papers")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();
  },
});

export const getByBranch = query({
  args: { branchId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("papers")
      .withIndex("by_branch", (q) => q.eq("branchId", args.branchId))
      .collect();
  },
});
