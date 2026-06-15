interface ValidationBadgeProps {
  groundednessScore: number;
  isValidated: boolean;
}

export function ValidationBadge({
  groundednessScore,
  isValidated,
}: ValidationBadgeProps) {
  const percentage = Math.round(groundednessScore * 100);

  // Color based on groundedness
  let colorClass: string;
  let label: string;

  if (percentage >= 95) {
    colorClass = "bg-green-100 text-green-800 border-green-200";
    label = "Verified";
  } else if (percentage >= 80) {
    colorClass = "bg-yellow-100 text-yellow-800 border-yellow-200";
    label = "Mostly Verified";
  } else {
    colorClass = "bg-red-100 text-red-800 border-red-200";
    label = "Low Confidence";
  }

  if (!isValidated) {
    colorClass = "bg-gray-100 text-gray-600 border-gray-200";
    label = "Not Validated";
  }

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}
    >
      <svg
        className="w-3 h-3"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
        />
      </svg>
      <span>{label}</span>
      {isValidated && (
        <span className="opacity-75">({percentage}%)</span>
      )}
    </div>
  );
}
