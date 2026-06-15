import { createTool } from "@convex-dev/agent";
import { z } from "zod";
import type { Id } from "../_generated/dataModel";
import { api } from "../_generated/api";

type PaperSearchResult = {
  paperId?: string;
  title?: string;
  abstract?: string;
  year?: number;
  groundedness?: number;
};

/**
 * Tool: Search Papers
 * Full-text search across papers and summaries in the research session
 */
export const searchPapers = createTool({
  description: `Search for papers in the research session by keyword, topic, or author.

WHEN TO USE:
- When the user asks about specific topics or papers
- When looking for papers related to a concept
- When searching for papers by author or year

Returns matching papers with titles, abstracts, and groundedness scores.`,
  args: z.object({
    query: z.string().describe("Search query for papers"),
    sessionId: z.string().describe("The session ID to search within"),
    limit: z.number().optional().describe("Max results to return (default 5)"),
  }),
  handler: async (ctx, args): Promise<string> => {
    const limit = args.limit ?? 5;
    const sessionId = args.sessionId as Id<"sessions">;

    // Get papers by querying the full graph and filtering
    let papers: Array<Record<string, unknown>> = [];
    try {
      const graphData = await ctx.runQuery(api.graph.getFullGraph, { sessionId });

      const queryLower = args.query.toLowerCase();
      papers = graphData.nodes
        .filter((n: { type: string; data: { title?: string; abstract?: string } }) =>
          n.type === "paper" && (
            n.data.title?.toLowerCase().includes(queryLower) ||
            n.data.abstract?.toLowerCase().includes(queryLower)
          )
        )
        .slice(0, limit)
        .map((n: { data: Record<string, unknown> }) => n.data);
    } catch (error) {
      return `Error searching papers: ${error instanceof Error ? error.message : "Unknown error"}`;
    }

    if (!papers || papers.length === 0) {
      return `No papers found matching "${args.query}" in this research session.`;
    }

    const formatted = (papers as PaperSearchResult[])
      .map(
        (p, i: number) =>
          `[${i + 1}] ${p.title || p.paperId || "Unknown paper"}
Year: ${p.year || "Unknown"}
Groundedness: ${p.groundedness ? (p.groundedness * 100).toFixed(0) + "%" : "Not validated"}
Abstract: ${p.abstract?.slice(0, 200) || "No abstract"}...
---`
      )
      .join("\n\n");

    return `Found ${papers.length} papers matching "${args.query}":\n\n${formatted}`;
  },
});

/**
 * Tool: Get Summary
 * Get the HaluGate-validated summary for a specific paper
 */
export const getSummary = createTool({
  description: `Get the validated summary for a specific paper by its ID or title.

WHEN TO USE:
- When the user asks for details about a specific paper
- When you need to cite a paper's findings
- When answering questions about a paper's content

Returns the paper's summary along with its groundedness score.`,
  args: z.object({
    paperId: z.string().describe("The paper ID to get the summary for"),
    sessionId: z.string().describe("The session ID"),
  }),
  handler: async (ctx, args): Promise<string> => {
    const sessionId = args.sessionId as Id<"sessions">;

    // Get the full graph and find the paper
    let graphData;
    try {
      graphData = await ctx.runQuery(api.graph.getFullGraph, { sessionId });
    } catch (error) {
      return `Error fetching paper data: ${error instanceof Error ? error.message : "Unknown error"}`;
    }

    const paperNode = graphData.nodes.find(
      (n: { type: string; id: string; data: { paperId?: string } }) =>
        n.type === "paper" &&
        (n.data.paperId === args.paperId || n.id === `paper:${args.paperId}`)
    );

    if (!paperNode) {
      return `Paper with ID "${args.paperId}" not found in this research session.`;
    }

    const data = paperNode.data as {
      title?: string;
      abstract?: string;
      year?: number;
      venue?: string;
      authors?: Array<{ name?: string }>;
      groundedness?: number;
      summaryText?: string;
      citationCount?: number;
    };

    const authors = data.authors
      ?.map((a) => a.name)
      .filter(Boolean)
      .join(", ");

    return `## ${data.title || args.paperId}

**Authors:** ${authors || "Unknown"}
**Year:** ${data.year || "Unknown"}
**Venue:** ${data.venue || "Unknown"}
**Citations:** ${data.citationCount || 0}
**Groundedness:** ${data.groundedness ? (data.groundedness * 100).toFixed(0) + "%" : "Not validated"}

### Summary
${data.summaryText || data.abstract || "No summary available."}`;
  },
});

/**
 * Tool: Get Hypotheses
 * Find hypotheses by topic or confidence level
 */
export const getHypotheses = createTool({
  description: `Find research hypotheses generated during the session.

WHEN TO USE:
- When the user asks about hypotheses or findings
- When looking for high-confidence conclusions
- When exploring what the research discovered

Returns hypotheses with confidence scores and supporting papers.`,
  args: z.object({
    sessionId: z.string().describe("The session ID"),
    topic: z.string().optional().describe("Filter by topic keyword"),
    minConfidence: z
      .number()
      .optional()
      .describe("Minimum confidence threshold (0-1)"),
    limit: z.number().optional().describe("Max results to return (default 10)"),
  }),
  handler: async (ctx, args): Promise<string> => {
    const sessionId = args.sessionId as Id<"sessions">;
    const limit = args.limit ?? 10;
    const minConfidence = args.minConfidence ?? 0;

    // Get the full graph
    let graphData;
    try {
      graphData = await ctx.runQuery(api.graph.getFullGraph, { sessionId });
    } catch (error) {
      return `Error fetching hypotheses: ${error instanceof Error ? error.message : "Unknown error"}`;
    }

    let hypotheses = graphData.nodes
      .filter((n: { type: string }) => n.type === "hypothesis")
      .map((n: { data: Record<string, unknown> }) => n.data as {
        hypothesisId: string;
        text: string;
        confidence: number;
        supportingPaperIds: string[];
      });

    // Filter by confidence
    hypotheses = hypotheses.filter(
      (h: { confidence: number }) => h.confidence >= minConfidence
    );

    // Filter by topic if provided
    if (args.topic) {
      const topicLower = args.topic.toLowerCase();
      hypotheses = hypotheses.filter((h: { text: string }) =>
        h.text.toLowerCase().includes(topicLower)
      );
    }

    // Sort by confidence and limit
    hypotheses = hypotheses
      .sort((a: { confidence: number }, b: { confidence: number }) => b.confidence - a.confidence)
      .slice(0, limit);

    if (hypotheses.length === 0) {
      return args.topic
        ? `No hypotheses found matching "${args.topic}" with confidence >= ${(minConfidence * 100).toFixed(0)}%.`
        : `No hypotheses found with confidence >= ${(minConfidence * 100).toFixed(0)}%.`;
    }

    const formatted = hypotheses
      .map(
        (h: { text: string; confidence: number; supportingPaperIds: string[] }, i: number) =>
          `[${i + 1}] Confidence: ${(h.confidence * 100).toFixed(0)}%
${h.text}
Supporting papers: ${h.supportingPaperIds.length}
---`
      )
      .join("\n\n");

    return `Found ${hypotheses.length} hypotheses:\n\n${formatted}`;
  },
});

/**
 * Tool: Get Research Context
 * Get an overview of the session's research state
 */
export const getResearchContext = createTool({
  description: `Get an overview of the research session's current state.

WHEN TO USE:
- At the start of a conversation to understand available data
- When the user asks about the research progress
- When you need to know what papers and hypotheses are available

Returns session stats, branch information, and key metrics.`,
  args: z.object({
    sessionId: z.string().describe("The session ID"),
  }),
  handler: async (ctx, args): Promise<string> => {
    const sessionId = args.sessionId as Id<"sessions">;

    // Get the full graph
    let graphData;
    let session;
    try {
      graphData = await ctx.runQuery(api.graph.getFullGraph, { sessionId });
      session = await ctx.runQuery(api.sessions.getById, { id: sessionId });
    } catch (error) {
      return `Error fetching research context: ${error instanceof Error ? error.message : "Unknown error"}`;
    }

    const { stats, nodes } = graphData;

    // Calculate average groundedness
    const papers = nodes.filter((n: { type: string }) => n.type === "paper");
    const groundednessValues = papers
      .map((p: { data: { groundedness?: number } }) => p.data.groundedness)
      .filter((g: number | undefined): g is number => g !== undefined);
    const avgGroundedness =
      groundednessValues.length > 0
        ? groundednessValues.reduce((a: number, b: number) => a + b, 0) /
          groundednessValues.length
        : 0;

    // Calculate average hypothesis confidence
    const hypotheses = nodes.filter((n: { type: string }) => n.type === "hypothesis");
    const confidenceValues = hypotheses.map(
      (h: { data: { confidence?: number } }) => h.data.confidence ?? 0
    );
    const avgConfidence =
      confidenceValues.length > 0
        ? confidenceValues.reduce((a: number, b: number) => a + b, 0) /
          confidenceValues.length
        : 0;

    // Get branch topics
    const branches = nodes.filter((n: { type: string }) => n.type === "branch");
    const branchTopics = branches
      .map((b: { data: { query?: string } }) => b.data.query)
      .filter((topic: string | undefined): topic is string => Boolean(topic))
      .slice(0, 5);

    return `## Research Session Overview

**Query:** ${session?.initialQuery || "Unknown"}
**Status:** ${session?.status || "Unknown"}

### Statistics
- **Papers:** ${stats.paperCount}
- **Summaries:** ${stats.summaryCount}
- **Hypotheses:** ${stats.hypothesisCount}
- **Branches:** ${stats.branchCount}

### Quality Metrics
- **Average Groundedness:** ${(avgGroundedness * 100).toFixed(0)}%
- **Average Hypothesis Confidence:** ${(avgConfidence * 100).toFixed(0)}%

### Research Branches
${branchTopics.map((t, i: number) => `${i + 1}. ${t}`).join("\n")}

Use the other tools to explore specific papers, summaries, or hypotheses.`;
  },
});
