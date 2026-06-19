interface StatusBadgeProps {
  status: string;
  compact?: boolean;
}

export function StatusBadge({ status, compact = false }: StatusBadgeProps) {
  const normalized = status.toLowerCase().replaceAll("_", "-");
  return (
    <span className={`status-badge status-${normalized}${compact ? " status-compact" : ""}`}>
      <span className="status-dot" aria-hidden="true" />
      {status.replaceAll("_", " ")}
    </span>
  );
}
