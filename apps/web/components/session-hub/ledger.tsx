"use client";
import { useMemo, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/format";
import { filterLedger, ledgerRows, uniquePapers } from "@/lib/session-hub.js";
import type { SessionSnapshot } from "@/lib/types";

const columns = [
  ["claim_text", "Claim"],
  ["status", "Status"],
  ["confidence", "Confidence"],
  ["paperTitle", "Source paper"],
  ["evidenceCount", "Evidence"],
  ["contradictionCount", "Contradictions"],
  ["branchLabel", "Branch"],
  ["created_at", "Created at"],
];
export function ClaimLedger({
  snapshot,
  select,
  selectedId,
}: {
  snapshot: SessionSnapshot;
  select: (type: string, id: string) => void;
  selectedId: string | null;
}) {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sort, setSort] = useState("created_at");
  const [ascending, setAscending] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const rows = useMemo(
    () => filterLedger(ledgerRows(snapshot), filters, sort, ascending),
    [snapshot, filters, sort, ascending],
  );
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pages - 1);
  const papers = uniquePapers(snapshot.papers);
  const options: [string, string, { value: string; label: string }[]][] = [
    [
      "status",
      "Status",
      [
        "supported",
        "weakly_supported",
        "contradicted",
        "not_found",
        "speculative",
        "needs_review",
      ].map((value) => ({ value, label: value.replaceAll("_", " ") })),
    ],
    [
      "paper",
      "Paper",
      papers.map((paper) => ({ value: paper.id, label: paper.title })),
    ],
    [
      "branch",
      "Branch",
      snapshot.branches.map((branch) => ({
        value: branch.id,
        label: branch.label || branch.query,
      })),
    ],
    [
      "type",
      "Claim type",
      [...new Set(snapshot.claims.map((claim) => claim.claim_type))]
        .sort()
        .map((value) => ({ value, label: value.replaceAll("_", " ") })),
    ],
    [
      "confidence",
      "Confidence",
      [
        { value: "high", label: "80% or higher" },
        { value: "low", label: "Below 80%" },
        { value: "unscored", label: "Unscored" },
      ],
    ],
    [
      "reviewed",
      "Review history",
      [
        { value: "reviewed", label: "Reviewed — check recorded" },
        { value: "unreviewed", label: "Unreviewed — no check" },
      ],
    ],
  ];
  function filter(key: string, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(0);
  }
  return (
    <div className="hub-ledger">
      <div className="hub-filters">
        <label className="hub-search">
          Find a claim
          <input
            type="search"
            value={filters.search || ""}
            onChange={(event) => filter("search", event.target.value)}
            placeholder="Search claim text"
          />
        </label>
        {options.map(([key, label, values]) => (
          <label key={key}>
            {label}
            <select
              value={filters[key] || ""}
              onChange={(event) => filter(key, event.target.value)}
            >
              <option value="">All</option>
              {values.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        ))}
        <button
          className="button button-small button-secondary"
          onClick={() => {
            setFilters({});
            setPage(0);
          }}
        >
          Clear filters
        </button>
      </div>
      <p className="hub-note">
        Review history indicates a recorded validation check, including
        retrieval-only checks. It does not indicate human approval. Unscored
        confidence is never treated as zero.
      </p>
      <div
        className="data-table-wrap hub-ledger-table"
        role="region"
        aria-label="Claim ledger"
        tabIndex={0}
      >
        <table className="data-table">
          <thead>
            <tr>
              {columns.map(([key, label]) => (
                <th
                  key={key}
                  scope="col"
                  aria-sort={
                    sort === key
                      ? ascending
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <button
                    onClick={() => {
                      setSort(key);
                      setAscending(sort === key ? !ascending : true);
                      setPage(0);
                    }}
                  >
                    {label}
                    {sort === key ? (ascending ? " ↑" : " ↓") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows
              .slice(currentPage * pageSize, (currentPage + 1) * pageSize)
              .map((row) => (
                <tr
                  key={row.id}
                  className={selectedId === row.id ? "hub-selected-row" : ""}
                >
                  <td>
                    <button
                      className="hub-text-button"
                      onClick={() => select("claim", row.id)}
                    >
                      {row.claim_text}
                    </button>
                    <small>{row.claim_type.replaceAll("_", " ")}</small>
                  </td>
                  <td>
                    <StatusBadge status={row.status} />
                  </td>
                  <td>
                    {row.confidence == null
                      ? "Unscored"
                      : `${Math.round(row.confidence * 100)}%`}
                  </td>
                  <td>
                    {row.paper_id ? (
                      <button
                        className="hub-text-button"
                        onClick={() => select("paper", row.paper_id!)}
                      >
                        {row.paperTitle}
                      </button>
                    ) : (
                      row.paperTitle
                    )}
                  </td>
                  <td>{row.evidenceCount}</td>
                  <td>{row.contradictionCount}</td>
                  <td>
                    {row.branch_id ? (
                      <button
                        className="hub-text-button"
                        onClick={() => select("branch", row.branch_id!)}
                      >
                        {row.branchLabel}
                      </button>
                    ) : (
                      row.branchLabel
                    )}
                  </td>
                  <td>
                    <time dateTime={row.created_at}>
                      {formatDate(row.created_at)}
                    </time>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="hub-note">
            {snapshot.claims.length
              ? "No claims match these filters."
              : "No claims yet. Start research to build the ledger."}
          </p>
        )}
      </div>
      <div className="hub-pagination">
        <span role="status">
          {rows.length ? currentPage * pageSize + 1 : 0}–
          {Math.min((currentPage + 1) * pageSize, rows.length)} of {rows.length}{" "}
          claims
        </span>
        <label>
          Rows per page
          <select
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(0);
            }}
          >
            {[10, 25, 50].map((size) => (
              <option key={size}>{size}</option>
            ))}
          </select>
        </label>
        <button
          className="button button-secondary button-small"
          disabled={currentPage === 0}
          onClick={() => setPage(currentPage - 1)}
        >
          Previous
        </button>
        <span>
          Page {currentPage + 1} of {pages}
        </span>
        <button
          className="button button-secondary button-small"
          disabled={currentPage + 1 >= pages}
          onClick={() => setPage(currentPage + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
