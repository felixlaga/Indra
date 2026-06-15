/**
 * Chat Actions
 *
 * Server actions for handling chat messages with the research agent.
 */

import { action, internalMutation } from "../_generated/server";
import { v } from "convex/values";
import { api, internal } from "../_generated/api";
import { researchChatAgent } from "./agent";
import type { Id } from "../_generated/dataModel";

type SendMessageResult = {
  messageId: Id<"chatMessages">;
  response: string;
  toolCalls: Array<{ toolName: string; input: unknown; output: unknown }>;
  citations: Array<{
    paperId: string;
    paperTitle: string;
    relevantText: string;
    groundedness: number;
  }>;
};

// Internal mutation to create a message (called from action)
export const createMessageInternal = internalMutation({
  args: {
    threadId: v.id("chatThreads"),
    role: v.union(v.literal("user"), v.literal("assistant")),
    content: v.string(),
    citations: v.optional(
      v.array(
        v.object({
          paperId: v.string(),
          paperTitle: v.string(),
          relevantText: v.string(),
          groundedness: v.number(),
        })
      )
    ),
    validation: v.optional(
      v.object({
        isValidated: v.boolean(),
        groundednessScore: v.number(),
        hallucinatedSpans: v.array(
          v.object({
            text: v.string(),
            start: v.number(),
            end: v.number(),
          })
        ),
      })
    ),
    toolCalls: v.optional(
      v.array(
        v.object({
          toolName: v.string(),
          input: v.optional(v.any()),
          output: v.optional(v.any()),
        })
      )
    ),
    isStreaming: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    // Update thread's updatedAt timestamp
    await ctx.db.patch(args.threadId, {
      updatedAt: Date.now(),
    });

    return await ctx.db.insert("chatMessages", {
      threadId: args.threadId,
      role: args.role,
      content: args.content,
      citations: args.citations,
      validation: args.validation,
      toolCalls: args.toolCalls,
      isStreaming: args.isStreaming,
      createdAt: Date.now(),
    });
  },
});

// Internal mutation to update a message
export const updateMessageInternal = internalMutation({
  args: {
    messageId: v.id("chatMessages"),
    content: v.optional(v.string()),
    citations: v.optional(
      v.array(
        v.object({
          paperId: v.string(),
          paperTitle: v.string(),
          relevantText: v.string(),
          groundedness: v.number(),
        })
      )
    ),
    validation: v.optional(
      v.object({
        isValidated: v.boolean(),
        groundednessScore: v.number(),
        hallucinatedSpans: v.array(
          v.object({
            text: v.string(),
            start: v.number(),
            end: v.number(),
          })
        ),
      })
    ),
    toolCalls: v.optional(
      v.array(
        v.object({
          toolName: v.string(),
          input: v.optional(v.any()),
          output: v.optional(v.any()),
        })
      )
    ),
    isStreaming: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const { messageId, ...updates } = args;
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

/**
 * Send a message to the research chat agent
 */
export const sendMessage = action({
  args: {
    threadId: v.id("chatThreads"),
    sessionId: v.id("sessions"),
    message: v.string(),
  },
  handler: async (ctx, args): Promise<SendMessageResult> => {
    // 0. Get the agent thread ID from our chatThread
    const chatThread = await ctx.runQuery(api.chat.threads.get, {
      threadId: args.threadId,
    });
    if (!chatThread) {
      throw new Error("Chat thread not found");
    }
    if (!chatThread.agentThreadId) {
      throw new Error("This is a legacy thread without agent support. Please start a new chat thread.");
    }

    // 1. Store the user message
    await ctx.runMutation(
      internal.chat.actions.createMessageInternal,
      {
        threadId: args.threadId,
        role: "user",
        content: args.message,
      }
    );

    // 2. Create a placeholder for the assistant message (streaming)
    const assistantMessageId = await ctx.runMutation(
      internal.chat.actions.createMessageInternal,
      {
        threadId: args.threadId,
        role: "assistant",
        content: "",
        isStreaming: true,
      }
    );

    // 3. Run the agent using the agent's thread ID
    const { thread } = await researchChatAgent.continueThread(ctx, {
      threadId: chatThread.agentThreadId,
    });

    // Build the message with session context
    const messageWithContext = `Session ID: ${args.sessionId}

User message: ${args.message}`;

    const result = await thread.generateText({
      prompt: messageWithContext,
    });

    // 4. Extract tool calls
    const toolCalls: Array<{ toolName: string; input: unknown; output: unknown }> =
      [];
    for (const step of result.steps) {
      for (const toolCall of step.toolCalls) {
        const typedToolCall = toolCall as typeof toolCall & {
          args?: unknown;
          input?: unknown;
        };
        const toolResult = step.toolResults?.find(
          (r) => r.toolCallId === toolCall.toolCallId
        ) as
          | {
              result?: unknown;
              output?: unknown;
            }
          | undefined;
        toolCalls.push({
          toolName: toolCall.toolName,
          input: typedToolCall.args ?? typedToolCall.input,
          output: toolResult?.result ?? toolResult?.output,
        });
      }
    }

    // 5. Extract citations from tool results
    const citations: Array<{
      paperId: string;
      paperTitle: string;
      relevantText: string;
      groundedness: number;
    }> = [];

    // Parse citations from getSummary and searchPapers tool results
    for (const tc of toolCalls) {
      if (tc.toolName === "getSummary" && tc.output) {
        const output = tc.output as string;
        // Extract paper info from markdown format
        const titleMatch = output.match(/^## (.+)$/m);
        const groundednessMatch = output.match(/\*\*Groundedness:\*\* (\d+)%/);
        const summaryMatch = output.match(/### Summary\n(.+)/s);

        if (titleMatch) {
          citations.push({
            paperId: (tc.input as { paperId?: string })?.paperId || "unknown",
            paperTitle: titleMatch[1],
            relevantText: summaryMatch?.[1]?.slice(0, 200) || "",
            groundedness: groundednessMatch
              ? parseInt(groundednessMatch[1]) / 100
              : 0.5,
          });
        }
      }
    }

    // 6. Validate with HaluGate (if available)
    let validation:
      | {
          isValidated: boolean;
          groundednessScore: number;
          hallucinatedSpans: Array<{ text: string; start: number; end: number }>;
        }
      | undefined;

    try {
      const validationResult = await ctx.runAction(
        api.chat.validation.validateResponse,
        {
          response: result.text,
          sessionId: args.sessionId,
          question: args.message,
        }
      );

      if (validationResult) {
        validation = {
          isValidated: true,
          groundednessScore: validationResult.groundednessScore,
          hallucinatedSpans: validationResult.hallucinatedSpans,
        };
      }
    } catch {
      // HaluGate not available, continue without validation
      console.log("[sendMessage] HaluGate validation skipped");
    }

    // 7. Update the assistant message with final content
    await ctx.runMutation(internal.chat.actions.updateMessageInternal, {
      messageId: assistantMessageId,
      content: result.text,
      citations: citations.length > 0 ? citations : undefined,
      validation,
      toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
      isStreaming: false,
    });

    return {
      messageId: assistantMessageId,
      response: result.text,
      toolCalls,
      citations,
    };
  },
});

/**
 * Start a new chat thread and send the first message
 */
export const startThread = action({
  args: {
    sessionId: v.id("sessions"),
    message: v.string(),
    title: v.optional(v.string()),
  },
  handler: async (
    ctx,
    args
  ): Promise<SendMessageResult & { threadId: Id<"chatThreads"> }> => {
    // 1. Create an agent thread first
    const { threadId: agentThreadId } = await researchChatAgent.createThread(ctx, {
      title: args.title || args.message.slice(0, 50),
    });

    // 2. Create our chatThread record with the agent thread ID
    const threadId: Id<"chatThreads"> = await ctx.runMutation(api.chat.threads.create, {
      sessionId: args.sessionId,
      agentThreadId,
      title: args.title || args.message.slice(0, 50),
    });

    // 3. Send the first message
    const result: SendMessageResult = await ctx.runAction(api.chat.actions.sendMessage, {
      threadId,
      sessionId: args.sessionId,
      message: args.message,
    });

    return {
      threadId,
      ...result,
    };
  },
});
