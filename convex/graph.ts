import { query } from "./_generated/server";
import { v } from "convex/values";

export const getFullGraph = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    const [branches, papers, summaries, hypotheses] = await Promise.all([
      ctx.db
        .query("branches")
        .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
        .collect(),
      ctx.db
        .query("papers")
        .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
        .collect(),
      ctx.db
        .query("summaries")
        .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
        .collect(),
      ctx.db
        .query("hypotheses")
        .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
        .collect(),
    ]);

    // Build groundedness map and summary text map for papers
    const groundednessMap = new Map<string, number>();
    const summaryTextMap = new Map<string, string>();
    for (const summary of summaries) {
      groundednessMap.set(summary.paperId, summary.groundedness);
      summaryTextMap.set(summary.paperId, summary.summary);
    }

    // Color helpers
    const groundednessToColor = (g: number) => {
      // Red (low) to Green (high)
      const r = Math.round(255 * (1 - g));
      const gr = Math.round(255 * g);
      return `rgb(${r}, ${gr}, 100)`;
    };

    const confidenceToColor = (c: number) => {
      // Purple gradient based on confidence
      const intensity = Math.round(100 + 155 * c);
      return `rgb(${intensity}, 85, 247)`;
    };

    const statusToColor = (status: string) => {
      switch (status) {
        case "running":
          return "#22d3ee"; // cyan
        case "completed":
          return "#22c55e"; // green
        case "paused":
          return "#f59e0b"; // amber
        case "pruned":
          return "#ef4444"; // red
        default:
          return "#3b82f6"; // blue
      }
    };

    // Build nodes
    const nodes: Array<{
      id: string;
      type: string;
      label: string;
      color: string;
      size: number;
      data: Record<string, unknown>;
    }> = [];

    // Branch nodes
    for (const branch of branches) {
      nodes.push({
        id: `branch:${branch.branchId}`,
        type: "branch",
        label: branch.query.slice(0, 50) + (branch.query.length > 50 ? "..." : ""),
        color: statusToColor(branch.status),
        size: 12 + Math.min(branch.paperCount, 10),
        data: {
          branchId: branch.branchId,
          query: branch.query,
          status: branch.status,
          mode: branch.mode,
          contextUtilization: branch.contextWindowUsed / branch.maxContextWindow,
          paperCount: branch.paperCount,
          summaryCount: branch.summaryCount,
          parentBranchId: branch.parentBranchId,
          createdAt: branch.createdAt,
        },
      });
    }

    // Paper nodes
    for (const paper of papers) {
      const groundedness = groundednessMap.get(paper.paperId) ?? 0.5;
      const summaryText = summaryTextMap.get(paper.paperId);
      nodes.push({
        id: `paper:${paper.paperId}`,
        type: "paper",
        label: paper.title?.slice(0, 40) ?? paper.paperId,
        color: groundednessToColor(groundedness),
        size: 4 + Math.min((paper.citationCount ?? 0) / 100, 6),
        data: {
          paperId: paper.paperId,
          title: paper.title,
          abstract: paper.abstract,
          year: paper.year,
          citationCount: paper.citationCount,
          venue: paper.venue,
          authors: paper.authors,
          groundedness,
          summaryText,
          iterationNumber: paper.iterationNumber,
          branchId: paper.branchId,
          createdAt: paper.createdAt,
        },
      });
    }

    // Hypothesis nodes
    for (const hyp of hypotheses) {
      nodes.push({
        id: `hyp:${hyp.hypothesisId}`,
        type: "hypothesis",
        label: hyp.text.slice(0, 50) + (hyp.text.length > 50 ? "..." : ""),
        color: confidenceToColor(hyp.confidence),
        size: 5 + hyp.confidence * 5,
        data: {
          hypothesisId: hyp.hypothesisId,
          text: hyp.text,
          confidence: hyp.confidence,
          supportingPaperIds: hyp.supportingPaperIds,
          iterationNumber: hyp.iterationNumber,
          branchId: hyp.branchId,
          createdAt: hyp.createdAt,
        },
      });
    }

    // Build links
    const links: Array<{
      source: string;
      target: string;
      type: string;
    }> = [];

    // Branch parent-child links
    for (const branch of branches) {
      if (branch.parentBranchId) {
        links.push({
          source: `branch:${branch.parentBranchId}`,
          target: `branch:${branch.branchId}`,
          type: "branch_split",
        });
      }
    }

    // Paper to branch links
    for (const paper of papers) {
      links.push({
        source: `branch:${paper.branchId}`,
        target: `paper:${paper.paperId}`,
        type: "paper_in_branch",
      });
    }

    // Hypothesis to branch links
    for (const hyp of hypotheses) {
      links.push({
        source: `branch:${hyp.branchId}`,
        target: `hyp:${hyp.hypothesisId}`,
        type: "hypothesis_from_branch",
      });

      // Hypothesis to supporting papers
      for (const paperId of hyp.supportingPaperIds) {
        // Check if paper node exists
        if (nodes.some((n) => n.id === `paper:${paperId}`)) {
          links.push({
            source: `paper:${paperId}`,
            target: `hyp:${hyp.hypothesisId}`,
            type: "hypothesis_support",
          });
        }
      }
    }

    return {
      nodes,
      links,
      stats: {
        branchCount: branches.length,
        paperCount: papers.length,
        summaryCount: summaries.length,
        hypothesisCount: hypotheses.length,
      },
    };
  },
});
