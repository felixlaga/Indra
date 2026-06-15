import { useState } from "react";

interface ToolCall {
  toolName: string;
  input: unknown;
  output: unknown;
}

interface ToolCallPanelProps {
  toolCalls: ToolCall[];
}

export function ToolCallPanel({ toolCalls }: ToolCallPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (toolCalls.length === 0) {
    return null;
  }

  // Tool icons/colors
  const toolStyles: Record<string, { icon: string; color: string }> = {
    searchPapers: { icon: "🔍", color: "text-blue-400" },
    getSummary: { icon: "📄", color: "text-green-400" },
    getHypotheses: { icon: "💡", color: "text-yellow-400" },
    getResearchContext: { icon: "📊", color: "text-purple-400" },
  };

  const formatToolValue = (value: unknown): string => {
    if (typeof value === "string") {
      return value;
    }
    return JSON.stringify(value, null, 2) ?? "";
  };

  return (
    <div className="mt-3 border-t border-gray-700 pt-3">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        <span>
          {toolCalls.length} tool{toolCalls.length > 1 ? "s" : ""} used
        </span>
        <div className="flex gap-1">
          {toolCalls.map((tc, i) => (
            <span key={i}>{toolStyles[tc.toolName]?.icon || "🔧"}</span>
          ))}
        </div>
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-2">
          {toolCalls.map((tc, i) => {
            const style = toolStyles[tc.toolName] || {
              icon: "🔧",
              color: "text-gray-400",
            };

            return (
              <div
                key={i}
                className="bg-gray-800/50 rounded p-2 text-xs font-mono"
              >
                <div className={`flex items-center gap-2 ${style.color}`}>
                  <span>{style.icon}</span>
                  <span className="font-medium">{tc.toolName}</span>
                </div>

                {/* Input */}
                <div className="mt-2">
                  <span className="text-gray-500">Input:</span>
                  <pre className="mt-1 text-gray-300 overflow-x-auto whitespace-pre-wrap">
                    {formatToolValue(tc.input)}
                  </pre>
                </div>

                {/* Output preview */}
                {tc.output !== undefined && tc.output !== null && (
                  <div className="mt-2">
                    <span className="text-gray-500">Output:</span>
                    <pre className="mt-1 text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-32 overflow-y-auto">
                      {formatToolValue(tc.output).slice(0, 500)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
