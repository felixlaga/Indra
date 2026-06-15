import { mutation, query } from "../_generated/server";
import { v } from "convex/values";

const citationValidator = v.object({
  paperId: v.string(),
  paperTitle: v.string(),
  relevantText: v.string(),
  groundedness: v.number(),
});

const validationValidator = v.object({
  isValidated: v.boolean(),
  groundednessScore: v.number(),
  hallucinatedSpans: v.array(
    v.object({
      text: v.string(),
      start: v.number(),
      end: v.number(),
    })
  ),
});

const toolCallValidator = v.object({
  toolName: v.string(),
  input: v.any(),
  output: v.any(),
});

export const create = mutation({
  args: {
    threadId: v.id("chatThreads"),
    role: v.union(v.literal("user"), v.literal("assistant")),
    content: v.string(),
    citations: v.optional(v.array(citationValidator)),
    validation: v.optional(validationValidator),
    toolCalls: v.optional(v.array(toolCallValidator)),
    isStreaming: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    // Update thread's updatedAt timestamp
    await ctx.db.patch(args.threadId, {
      updatedAt: Date.now(),
    });

    const messageId = await ctx.db.insert("chatMessages", {
      threadId: args.threadId,
      role: args.role,
      content: args.content,
      citations: args.citations,
      validation: args.validation,
      toolCalls: args.toolCalls,
      isStreaming: args.isStreaming,
      createdAt: Date.now(),
    });
    return messageId;
  },
});

export const listForThread = query({
  args: { threadId: v.id("chatThreads") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("chatMessages")
      .withIndex("by_thread_created", (q) => q.eq("threadId", args.threadId))
      .collect();
  },
});

export const get = query({
  args: { messageId: v.id("chatMessages") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.messageId);
  },
});

export const update = mutation({
  args: {
    messageId: v.id("chatMessages"),
    content: v.optional(v.string()),
    citations: v.optional(v.array(citationValidator)),
    validation: v.optional(validationValidator),
    toolCalls: v.optional(v.array(toolCallValidator)),
    isStreaming: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const { messageId, ...updates } = args;
    // Filter out undefined values
    const filteredUpdates: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(updates)) {
      if (value !== undefined) {
        filteredUpdates[key] = value;
      }
    }
    if (Object.keys(filteredUpdates).length > 0) {
      await ctx.db.patch(messageId, filteredUpdates);
    }
  },
});

export const appendContent = mutation({
  args: {
    messageId: v.id("chatMessages"),
    contentChunk: v.string(),
  },
  handler: async (ctx, args) => {
    const message = await ctx.db.get(args.messageId);
    if (!message) {
      throw new Error("Message not found");
    }
    await ctx.db.patch(args.messageId, {
      content: message.content + args.contentChunk,
    });
  },
});

export const finishStreaming = mutation({
  args: {
    messageId: v.id("chatMessages"),
    finalContent: v.string(),
    citations: v.optional(v.array(citationValidator)),
    validation: v.optional(validationValidator),
    toolCalls: v.optional(v.array(toolCallValidator)),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.messageId, {
      content: args.finalContent,
      citations: args.citations,
      validation: args.validation,
      toolCalls: args.toolCalls,
      isStreaming: false,
    });
  },
});
