/**
 * HaluGate Validation Integration
 *
 * Validates agent responses against research data using the HaluGate server.
 */

import { action, query } from "../_generated/server";
import { v } from "convex/values";

// HaluGate server URL must be set in the Convex environment.
const HALUGATE_URL = process.env.HALUGATE_URL;

interface HaluGateResponse {
  groundedness_score: number;
  hallucinated_spans: Array<{
    text: string;
    start: number;
    end: number;
    confidence: number;
  }>;
  validation_details: {
    total_claims: number;
    supported_claims: number;
    unsupported_claims: number;
  };
}

/**
 * Get context from the research session for validation
 */
export const getValidationContext = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    // Get summaries for context
    const summaries = await ctx.db
      .query("summaries")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();

    // Get papers for abstracts
    const papers = await ctx.db
      .query("papers")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();

    // Build context string
    const contextParts: string[] = [];

    // Add summaries
    for (const summary of summaries) {
      contextParts.push(`Paper: ${summary.paperTitle}\nSummary: ${summary.summary}`);
    }

    // Add paper abstracts
    for (const paper of papers) {
      if (paper.abstract) {
        contextParts.push(
          `Paper: ${paper.title || paper.paperId}\nAbstract: ${paper.abstract}`
        );
      }
    }

    return contextParts.join("\n\n---\n\n");
  },
});

/**
 * Validate a response using HaluGate
 */
export const validateResponse = action({
  args: {
    response: v.string(),
    sessionId: v.id("sessions"),
    question: v.string(),
  },
  handler: async (
    ctx,
    args
  ): Promise<{
    groundednessScore: number;
    hallucinatedSpans: Array<{ text: string; start: number; end: number }>;
    isValid: boolean;
  } | null> => {
    // Get context from the research session
    const context = await ctx.runQuery(
      // @ts-expect-error - Dynamic API access
      ctx.api.chat.validation.getValidationContext,
      { sessionId: args.sessionId }
    );

    if (!context) {
      console.log("[validateResponse] No context available for validation");
      return null;
    }

    if (!HALUGATE_URL) {
      console.error("[validateResponse] HALUGATE_URL is not configured");
      return null;
    }

    try {
      const response = await fetch(`${HALUGATE_URL}/validate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          response: args.response,
          context: context,
          question: args.question,
        }),
      });

      if (!response.ok) {
        console.error(
          `[validateResponse] HaluGate error: ${response.status} ${response.statusText}`
        );
        return null;
      }

      const result: HaluGateResponse = await response.json();

      return {
        groundednessScore: result.groundedness_score,
        hallucinatedSpans: result.hallucinated_spans.map((span) => ({
          text: span.text,
          start: span.start,
          end: span.end,
        })),
        isValid: result.groundedness_score >= 0.8,
      };
    } catch (error) {
      console.error("[validateResponse] Failed to validate:", error);
      return null;
    }
  },
});

/**
 * Retry validation with stricter guidance
 *
 * If initial validation fails (groundedness < 95%), this can be used
 * to regenerate the response with more specific instructions.
 */
export const getStricterGuidance = action({
  args: {
    originalResponse: v.string(),
    hallucinatedSpans: v.array(
      v.object({
        text: v.string(),
        start: v.number(),
        end: v.number(),
      })
    ),
    groundednessScore: v.number(),
  },
  handler: async (_ctx, args): Promise<string> => {
    const spanTexts = args.hallucinatedSpans.map((s) => `"${s.text}"`).join(", ");

    return `Your previous response had a groundedness score of ${(args.groundednessScore * 100).toFixed(0)}%.

The following parts were flagged as potentially unsupported by the source material:
${spanTexts}

Please revise your response to:
1. Remove or rephrase unsupported claims
2. Only include information that is directly supported by the research papers
3. When uncertain, clearly state the level of confidence
4. Use citations to indicate which papers support each claim

Original response to revise:
${args.originalResponse}`;
  },
});
