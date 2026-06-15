import { useState } from "react";

interface Citation {
  paperId: string;
  paperTitle: string;
  relevantText: string;
  groundedness: number;
}

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export function CitationCard({ citation, index }: CitationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const percentage = Math.round(citation.groundedness * 100);

  // Color based on groundedness
  const progressColor =
    percentage >= 80
      ? "bg-green-500"
      : percentage >= 60
        ? "bg-yellow-500"
        : "bg-red-500";

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-3 flex items-start gap-3 text-left hover:bg-gray-700/50 transition-colors"
      >
        {/* Citation number */}
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-medium flex items-center justify-center">
          {index + 1}
        </span>

        <div className="flex-1 min-w-0">
          {/* Paper title */}
          <h4 className="text-sm font-medium text-white truncate">
            {citation.paperTitle}
          </h4>

          {/* Groundedness bar */}
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-gray-600 rounded-full overflow-hidden">
              <div
                className={`h-full ${progressColor} rounded-full`}
                style={{ width: `${percentage}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">{percentage}%</span>
          </div>
        </div>

        {/* Expand icon */}
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-gray-700">
          <p className="mt-3 text-sm text-gray-300 leading-relaxed">
            {citation.relevantText}
          </p>

          {/* Link to paper (if using Semantic Scholar) */}
          <a
            href={`https://www.semanticscholar.org/paper/${citation.paperId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            <span>View on Semantic Scholar</span>
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
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>
      )}
    </div>
  );
}
