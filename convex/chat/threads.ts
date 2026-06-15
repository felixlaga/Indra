import { mutation, query } from "../_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    sessionId: v.id("sessions"),
    agentThreadId: v.optional(v.string()),
    title: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    const threadId = await ctx.db.insert("chatThreads", {
      sessionId: args.sessionId,
      agentThreadId: args.agentThreadId,
      title: args.title,
      createdAt: now,
      updatedAt: now,
    });
    return threadId;
  },
});

export const get = query({
  args: { threadId: v.id("chatThreads") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.threadId);
  },
});

export const listForSession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("chatThreads")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .order("desc")
      .collect();
  },
});

export const updateTitle = mutation({
  args: {
    threadId: v.id("chatThreads"),
    title: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.threadId, {
      title: args.title,
      updatedAt: Date.now(),
    });
  },
});

export const remove = mutation({
  args: { threadId: v.id("chatThreads") },
  handler: async (ctx, args) => {
    // Delete all messages in the thread first
    const messages = await ctx.db
      .query("chatMessages")
      .withIndex("by_thread", (q) => q.eq("threadId", args.threadId))
      .collect();

    for (const msg of messages) {
      await ctx.db.delete(msg._id);
    }

    // Then delete the thread
    await ctx.db.delete(args.threadId);
  },
});

export const touch = mutation({
  args: { threadId: v.id("chatThreads") },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.threadId, {
      updatedAt: Date.now(),
    });
  },
});
