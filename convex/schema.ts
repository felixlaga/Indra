import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  // Research Sessions
  sessions: defineTable({
    sessionId: v.string(),
    initialQuery: v.string(),
    status: v.union(
      v.literal("pending"),
      v.literal("running"),
      v.literal("completed"),
      v.literal("failed")
    ),
    createdAt: v.number(),
    updatedAt: v.number(),
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
  })
    .index("by_session_id", ["sessionId"])
    .index("by_status", ["status"]),

  // Branches
  branches: defineTable({
    sessionId: v.id("sessions"),
    branchId: v.string(),
    query: v.string(),
    mode: v.union(v.literal("search_summarize"), v.literal("hypothesis")),
    status: v.union(
      v.literal("pending"),
      v.literal("running"),
      v.literal("completed"),
      v.literal("paused"),
      v.literal("pruned")
    ),
    parentBranchId: v.optional(v.string()),
    contextWindowUsed: v.number(),
    maxContextWindow: v.number(),
    paperCount: v.number(),
    summaryCount: v.number(),
    createdAt: v.number(),
    updatedAt: v.number(),
  })
    .index("by_session", ["sessionId"])
    .index("by_branch_id", ["branchId"])
    .index("by_parent", ["parentBranchId"]),

  // Papers
  papers: defineTable({
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
    createdAt: v.number(),
  })
    .index("by_session", ["sessionId"])
    .index("by_branch", ["branchId"])
    .index("by_paper_id", ["paperId"]),

  // Validated Summaries
  summaries: defineTable({
    sessionId: v.id("sessions"),
    branchId: v.string(),
    paperId: v.string(),
    paperTitle: v.string(),
    summary: v.string(),
    groundedness: v.number(),
    iterationNumber: v.number(),
    createdAt: v.number(),
  })
    .index("by_session", ["sessionId"])
    .index("by_branch", ["branchId"])
    .index("by_paper", ["paperId"]),

  // Hypotheses
  hypotheses: defineTable({
    sessionId: v.id("sessions"),
    branchId: v.string(),
    hypothesisId: v.string(),
    text: v.string(),
    supportingPaperIds: v.array(v.string()),
    confidence: v.number(),
    iterationNumber: v.number(),
    createdAt: v.number(),
  })
    .index("by_session", ["sessionId"])
    .index("by_branch", ["branchId"])
    .index("by_confidence", ["confidence"]),

  // Realtime Events (for streaming to frontend)
  events: defineTable({
    sessionId: v.id("sessions"),
    eventType: v.string(),
    payload: v.any(),
    branchId: v.optional(v.string()),
    createdAt: v.number(),
  })
    .index("by_session", ["sessionId"])
    .index("by_session_created", ["sessionId", "createdAt"]),

  // Chat Threads for research discussions
  chatThreads: defineTable({
    sessionId: v.id("sessions"),
    agentThreadId: v.optional(v.string()), // Agent component's internal thread ID
    title: v.optional(v.string()),
    createdAt: v.number(),
    updatedAt: v.number(),
  }).index("by_session", ["sessionId"]),

  // Chat Messages with citations and validation
  chatMessages: defineTable({
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
    createdAt: v.number(),
  })
    .index("by_thread", ["threadId"])
    .index("by_thread_created", ["threadId", "createdAt"]),
});
