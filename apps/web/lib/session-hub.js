/** Shared, deterministic read models for the session hub. */
/** @typedef {import('./types').SessionSnapshot} SessionSnapshot */
/** @typedef {{status?: string, paper?: string, branch?: string, type?: string, confidence?: string, reviewed?: string, search?: string}} LedgerFilters */

/** @param {SessionSnapshot} snapshot */
export function ledgerRows(snapshot) {
  const papers = new Map(
    snapshot.papers.map((entry) => [entry.paper_id, entry.paper]),
  );
  const branches = new Map(
    snapshot.branches.map((branch) => [branch.id, branch]),
  );
  const checked = new Set(
    [...(snapshot.validated_claim_ids ?? []), ...snapshot.events
      .filter((event) => event.event_type === "claim_validated")
      .map((event) => event.payload.claim_id)],
  );
  const evidence = new Map();
  for (const item of snapshot.claim_evidence) {
    const counts = evidence.get(item.claim_id) ?? {
      evidenceCount: 0,
      contradictionCount: 0,
    };
    counts.evidenceCount++;
    if (item.relation === "contradicts") counts.contradictionCount++;
    evidence.set(item.claim_id, counts);
  }
  return snapshot.claims.map((claim) => ({
    ...claim,
    paperTitle: papers.get(claim.paper_id ?? "")?.title ?? "No source paper",
    branchLabel: branches.get(claim.branch_id ?? "")?.label || "No branch",
    reviewed: checked.has(claim.id),
    ...(evidence.get(claim.id) ?? { evidenceCount: 0, contradictionCount: 0 }),
  }));
}

/** @param {ReturnType<typeof ledgerRows>} rows @param {LedgerFilters} filters @param {string} sort @param {boolean} ascending */
export function filterLedger(
  rows,
  filters,
  sort = "created_at",
  ascending = false,
) {
  const selected = rows.filter((row) => {
    if (filters.status && row.status !== filters.status) return false;
    if (filters.paper && row.paper_id !== filters.paper) return false;
    if (filters.branch && row.branch_id !== filters.branch) return false;
    if (filters.type && row.claim_type !== filters.type) return false;
    if (filters.reviewed && row.reviewed !== (filters.reviewed === "reviewed"))
      return false;
    if (filters.confidence === "unscored" && row.confidence != null)
      return false;
    if (
      filters.confidence === "high" &&
      (row.confidence == null || row.confidence < 0.8)
    )
      return false;
    if (
      filters.confidence === "low" &&
      (row.confidence == null || row.confidence >= 0.8)
    )
      return false;
    return (
      !filters.search ||
      row.claim_text.toLowerCase().includes(filters.search.toLowerCase())
    );
  });
  const field = /** @type {keyof ReturnType<typeof ledgerRows>[number]} */ (
    sort
  );
  return selected.sort((a, b) => {
    const left = a[field],
      right = b[field];
    // Unscored confidence always sorts last, in either direction.
    if (left == null || right == null)
      return left == null ? (right == null ? a.id.localeCompare(b.id) : 1) : -1;
    const result =
      typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left).localeCompare(String(right));
    return (ascending ? result : -result) || a.id.localeCompare(b.id);
  });
}

/** @param {import('./types').SessionPaperView[]} entries */
export function uniquePapers(entries) {
  return [
    ...new Map(entries.map((entry) => [entry.paper_id, entry.paper])).values(),
  ];
}

/** @param {import('./types').Paper[]} papers */
export function timelineGroups(papers) {
  const years = [...new Set(papers.map((paper) => paper.year ?? null))].sort(
    (a, b) => (b ?? -Infinity) - (a ?? -Infinity),
  );
  return years.map((year) => ({
    year,
    papers: papers
      .filter((paper) => (paper.year ?? null) === year)
      .sort((a, b) => a.title.localeCompare(b.title)),
  }));
}

/** Stable cells prevent label overlap, including same-year papers. @param {import('./types').ResearchMapNode[]} nodes */
export function graphPositions(nodes) {
  const columns = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
  const sorted = [...nodes].sort(
    (a, b) =>
      (a.year ?? 9999) - (b.year ?? 9999) ||
      a.paper_id.localeCompare(b.paper_id),
  );
  const width = Math.max(660, columns * 220);
  const rows = Math.ceil(nodes.length / columns);
  const height = Math.max(360, rows * 125);
  return {
    width,
    height,
    nodes: sorted.map((node, index) => ({
      ...node,
      x: (width - columns * 220) / 2 + 110 + (index % columns) * 220,
      y: (height - rows * 125) / 2 + 52 + Math.floor(index / columns) * 125,
      radius:
        8 + Math.min(14, Math.log1p(Math.max(0, node.citation_count)) * 2),
    })),
  };
}

/** @param {SessionSnapshot} snapshot */
export function evidenceEdges(snapshot) {
  const claims = new Map(snapshot.claims.map((claim) => [claim.id, claim]));
  const pairs = new Map();
  for (const item of snapshot.claim_evidence) {
    const claim = claims.get(item.claim_id);
    if (
      !claim?.paper_id ||
      !item.paper_id ||
      claim.paper_id === item.paper_id ||
      !["supports", "contradicts", "weakly_supports"].includes(item.relation)
    )
      continue;
    const key = `${item.paper_id}:${claim.paper_id}:${item.relation}`;
    const edge = pairs.get(key) ?? {
      id: key,
      source_paper_id: item.paper_id,
      target_paper_id: claim.paper_id,
      relation: item.relation,
      claimIds: [],
    };
    if (!edge.claimIds.includes(claim.id)) edge.claimIds.push(claim.id);
    pairs.set(key, edge);
  }
  return [...pairs.values()];
}

/** Present saved validation details without dumping provider JSON into the UI. @param {string | null | undefined} notes */
export function validationSummary(notes) {
  if (!notes) return "No additional notes recorded.";
  try {
    const parsed = JSON.parse(notes);
    if (!parsed || typeof parsed !== "object") return notes;
    const strategy =
      parsed.strategy === "retrieval_only"
        ? "Retrieved passages only; no model judgment."
        : parsed.strategy === "structured_evidence_judge_v1"
          ? "Structured model evidence check."
          : "Recorded evidence check.";
    const rationales = Array.isArray(parsed.judgments)
      ? [
          ...new Set(
            parsed.judgments
              .map(
                (/** @type {{rationale?:unknown} | null} */ item) =>
                  item?.rationale,
              )
              .filter(
                (/** @type {unknown} */ item) => typeof item === "string",
              ),
          ),
        ]
      : [];
    return [
      strategy,
      typeof parsed.candidates_considered === "number"
        ? `${parsed.candidates_considered} candidate passages considered.`
        : "",
      ...rationales,
    ]
      .filter(Boolean)
      .join(" ");
  } catch {
    return notes;
  }
}
