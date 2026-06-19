export interface ContradictionCandidate {
  id: string;
  kind: "evidence_contradiction" | "opposing_claim_candidate";
  status: "observed" | "candidate";
  claim_ids: string[];
  paper_ids: string[];
  branch_ids: string[];
  description: string;
  rationale: string;
  score: number;
}

export interface WeakEvidenceItem {
  claim_id: string;
  claim_text: string;
  claim_status: string;
  confidence?: number | null;
  paper_id?: string | null;
  branch_id?: string | null;
  evidence_count: number;
  reason: string;
  priority: "high" | "medium" | "low";
}

export interface ResearchGap {
  id: string;
  gap_type: "claim_evidence" | "branch_grounding" | "paper_claim_coverage" | "citation_metadata";
  title: string;
  description: string;
  score: number;
  claim_ids: string[];
  paper_ids: string[];
  branch_ids: string[];
  caveat: string;
}

export interface OpenProblem {
  id: string;
  text: string;
  source: "limitation_claim" | "recommendation_claim" | "gap_signal";
  status: "speculative";
  score: number;
  claim_ids: string[];
  paper_ids: string[];
  branch_ids: string[];
  missing_evidence: string[];
}

export interface AdvisorRecommendation {
  id: string;
  priority: "high" | "medium" | "low";
  title: string;
  action: string;
  rationale: string;
  claim_ids: string[];
  paper_ids: string[];
  branch_ids: string[];
}

export interface HypothesisProposal {
  id: string;
  text: string;
  status: "speculative";
  rationale: string;
  confidence: number;
  testability: number;
  risk: "low" | "medium" | "high" | "unknown";
  source_open_problem_id: string;
  supporting_claim_ids: string[];
  supporting_paper_ids: string[];
  missing_evidence: string[];
  next_steps: string[];
}

export interface ResearchAdviceOverview {
  text: string;
  contradiction_count: number;
  gap_count: number;
  weak_evidence_count: number;
  open_problem_count: number;
  hypothesis_count: number;
  caveats: string[];
}

export interface ResearchAdvice {
  session_id: string;
  contradictions: ContradictionCandidate[];
  weak_evidence: WeakEvidenceItem[];
  gaps: ResearchGap[];
  open_problems: OpenProblem[];
  recommendations: AdvisorRecommendation[];
  hypotheses: HypothesisProposal[];
  overview: ResearchAdviceOverview;
}
