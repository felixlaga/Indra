import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const emit = mutation({
  args: {
    sessionId: v.id("sessions"),
    eventType: v.string(),
    payload: v.any(),
    branchId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("events", {
      sessionId: args.sessionId,
      eventType: args.eventType,
      payload: args.payload,
      branchId: args.branchId,
      createdAt: Date.now(),
    });
  },
});

export const subscribe = query({
  args: {
    sessionId: v.id("sessions"),
    since: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const events = await ctx.db
      .query("events")
      .withIndex("by_session_created", (q) => q.eq("sessionId", args.sessionId))
      .order("desc")
      .take(100);
    return events.reverse();
  },
});

export const getLatest = query({
  args: {
    sessionId: v.id("sessions"),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 50;
    const events = await ctx.db
      .query("events")
      .withIndex("by_session_created", (q) => q.eq("sessionId", args.sessionId))
      .order("desc")
      .take(limit);
    return events;
  },
});

export const getAllForSession = query({
  args: {
    sessionId: v.id("sessions"),
  },
  handler: async (ctx, args) => {
    const events = await ctx.db
      .query("events")
      .withIndex("by_session_created", (q) => q.eq("sessionId", args.sessionId))
      .order("asc")
      .collect();
    return events;
  },
});
