import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    sessionId: v.string(),
    initialQuery: v.string(),
    parameters: v.optional(
      v.object({
        profile: v.optional(v.string()),
        max_iterations: v.optional(v.number()),
        start_date: v.optional(v.string()),
        end_date: v.optional(v.string()),
        use_managing_agent: v.optional(v.boolean()),
        sources: v.optional(v.array(v.string())),
      })
    ),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("sessions", {
      sessionId: args.sessionId,
      initialQuery: args.initialQuery,
      status: "running",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      parameters: args.parameters,
    });
  },
});

export const get = query({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("sessions")
      .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
      .first();
  },
});

export const getById = query({
  args: { id: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.id);
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("sessions").order("desc").take(20);
  },
});

export const updateStatus = mutation({
  args: {
    sessionId: v.string(),
    status: v.union(
      v.literal("pending"),
      v.literal("running"),
      v.literal("completed"),
      v.literal("failed")
    ),
  },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("sessions")
      .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
      .first();
    if (!session) return null;

    await ctx.db.patch(session._id, {
      status: args.status,
      updatedAt: Date.now(),
    });
    return session._id;
  },
});
