import test from "node:test";
import assert from "node:assert/strict";
import {
  ledgerRows,
  filterLedger,
  timelineGroups,
  uniquePapers,
  evidenceEdges,
} from "../lib/session-hub.js";
const snapshot = {
  papers: [
    { paper_id: "p1", paper: { id: "p1", title: "Source", year: 2020 } },
    { paper_id: "p1", paper: { id: "p1", title: "Source", year: 2020 } },
    { paper_id: "p2", paper: { id: "p2", title: "Undated", year: null } },
  ],
  branches: [{ id: "b", label: "Root" }],
  claims: [
    {
      id: "a",
      claim_text: "Supported statement",
      paper_id: "p1",
      branch_id: "b",
      status: "supported",
      claim_type: "factual",
      confidence: 0.9,
      created_at: "2026-01-01",
    },
    {
      id: "b",
      claim_text: "Unknown statement",
      paper_id: "p2",
      branch_id: "b",
      status: "needs_review",
      claim_type: "comparison",
      confidence: null,
      created_at: "2026-01-02",
    },
    {
      id: "c",
      claim_text: "Contradicted statement",
      paper_id: "p1",
      status: "contradicted",
      claim_type: "factual",
      confidence: 0.6,
      created_at: "2026-01-03",
    },
  ],
  events: [{ event_type: "claim_validated", payload: { claim_id: "a" } }],
  claim_evidence: [
    { id: "e1", claim_id: "a", paper_id: "p2", relation: "supports" },
    { id: "e2", claim_id: "a", paper_id: "p2", relation: "supports" },
    { id: "e3", claim_id: "c", paper_id: "p2", relation: "contradicts" },
    { id: "e4", claim_id: "c", paper_id: "p1", relation: "mentions" },
  ],
};
test("ledger counts persisted evidence and checks without inferring review from status", () => {
  const rows = ledgerRows(snapshot);
  assert.equal(rows[0].evidenceCount, 2);
  assert.equal(rows[0].reviewed, true);
  assert.equal(rows[2].reviewed, false);
  assert.equal(rows[2].contradictionCount, 1);
  assert.equal(rows[1].confidence, null);
});
test("all six filters compose and search is case insensitive", () => {
  const rows = ledgerRows(snapshot);
  assert.deepEqual(
    filterLedger(rows, {
      status: "supported",
      paper: "p1",
      branch: "b",
      type: "factual",
      confidence: "high",
      reviewed: "reviewed",
      search: "STATEMENT",
    }).map((row) => row.id),
    ["a"],
  );
  assert.equal(
    filterLedger(rows, { status: "supported", paper: "p2" }).length,
    0,
  );
  assert.deepEqual(
    filterLedger(rows, { confidence: "unscored", reviewed: "unreviewed" }).map(
      (row) => row.id,
    ),
    ["b"],
  );
  assert.deepEqual(
    filterLedger(rows, { confidence: "low" }).map((row) => row.id),
    ["c"],
  );
});

test("review filters retain checks outside the recent event window", () => {
  const rows = ledgerRows({ ...snapshot, events: [], validated_claim_ids: ["b"] });
  assert.equal(rows.find((row) => row.id === "b").reviewed, true);
  assert.equal(rows.find((row) => row.id === "a").reviewed, false);
});
test("confidence sort leaves unscored last in either direction without mutating input", () => {
  const rows = ledgerRows(snapshot);
  assert.deepEqual(
    filterLedger(rows, {}, "confidence", true).map((row) => row.id),
    ["c", "a", "b"],
  );
  assert.deepEqual(
    filterLedger(rows, {}, "confidence", false).map((row) => row.id),
    ["a", "c", "b"],
  );
  assert.deepEqual(
    rows.map((row) => row.id),
    ["a", "b", "c"],
  );
});
test("timeline deduplicates shared papers and preserves undated entries", () => {
  const papers = uniquePapers(snapshot.papers);
  assert.equal(papers.length, 2);
  assert.deepEqual(
    timelineGroups(papers).map((group) => group.year),
    [2020, null],
  );
});
test("evidence edges deduplicate claims and exclude mentions and self links", () => {
  const edges = evidenceEdges(snapshot);
  assert.equal(edges.length, 2);
  assert.deepEqual(edges[0].claimIds, ["a"]);
  assert.equal(edges[1].relation, "contradicts");
  assert.equal(edges[1].source_paper_id, "p2");
  assert.equal(edges[1].target_paper_id, "p1");
});

test("validation summaries retain rationales without displaying raw JSON", async () => {
  const { validationSummary } = await import("../lib/session-hub.js");
  const text = validationSummary(
    JSON.stringify({
      strategy: "retrieval_only",
      candidates_considered: 4,
      judgments: [
        { rationale: "Requires review." },
        { rationale: "Requires review." },
      ],
    }),
  );
  assert.match(text, /no model judgment/);
  assert.match(text, /4 candidate/);
  assert.equal(text.match(/Requires review/g).length, 1);
  assert.equal(validationSummary("Reviewer note."), "Reviewer note.");
});
