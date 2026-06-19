interface StatusBadgeProps {
  status: string;
  compact?: boolean;
}

const statusAliases: Record<string, string> = {
  supports: "supported",
  weakly_supports: "weakly_supported",
  contradicts: "contradicted",
  mentions: "needs_review",
  insufficient: "not_found",
};

export function StatusBadge({ status, compact = false }: StatusBadgeProps) {
  const styleStatus = statusAliases[status] ?? status;
  const normalized = styleStatus.toLowerCase().replaceAll("_", "-");
  return (
    <span className={`status-badge status-${normalized}${compact ? " status-compact" : ""}`}>
      <span className="status-dot" aria-hidden="true" />
      {status.replaceAll("_", " ")}
    </span>
  );
}
