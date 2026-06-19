import type { ClaimValidationTrace } from "@/lib/types";

export interface ParsedValidationNotes {
  strategy?: string;
  top_k?: number;
  min_score?: number;
  candidates_considered?: number;
  retrieved?: Array<{
    paper_id?: string;
    source_type?: string;
    relation?: string;
    score?: number;
    retrieval_score?: number;
    overlap_terms?: string[];
  }>;
  raw?: string;
}

export function parseValidationNotes(
  trace: Pick<ClaimValidationTrace, "notes">,
): ParsedValidationNotes | null {
  if (!trace.notes) return null;
  try {
    const parsed = JSON.parse(trace.notes) as unknown;
    if (typeof parsed === "object" && parsed !== null) {
      return parsed as ParsedValidationNotes;
    }
  } catch {
    return { raw: trace.notes };
  }
  return { raw: trace.notes };
}

export function evidenceLocationLabel(evidence: {
  source_type: string;
  metadata_field?: string | null;
  section_title?: string | null;
  page_start?: number | null;
  page_end?: number | null;
}): string {
  const source = evidence.source_type.replaceAll("_", " ");
  const parts = [evidence.section_title || evidence.metadata_field || source];
  if (evidence.page_start != null) {
    parts.push(
      evidence.page_end != null && evidence.page_end !== evidence.page_start
        ? `pages ${evidence.page_start}–${evidence.page_end}`
        : `page ${evidence.page_start}`,
    );
  }
  return parts.join(" · ");
}

export function claimPolicyMessage(status: string): string {
  switch (status) {
    case "supported":
      return "This claim has supporting source evidence and may be used in synthesis with its citation attached.";
    case "weakly_supported":
      return "This claim has partial evidence. Use cautious language and inspect the passages before synthesis.";
    case "contradicted":
      return "Source evidence conflicts with this claim. Preserve and surface the contradiction; do not present the claim as fact.";
    case "not_found":
      return "No sufficiently relevant source passage was found. The claim must not be promoted as factual.";
    case "speculative":
      return "This is a speculative claim. It remains labeled as a hypothesis until explicit evidence is supplied.";
    default:
      return "This claim still requires evidence review before it can be used as factual output.";
  }
}
