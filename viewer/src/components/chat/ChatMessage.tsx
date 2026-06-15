import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ValidationBadge } from "./ValidationBadge";
import { CitationCard } from "./CitationCard";
import { ToolCallPanel } from "./ToolCallPanel";

interface Citation {
  paperId: string;
  paperTitle: string;
  relevantText: string;
  groundedness: number;
}

interface ToolCall {
  toolName: string;
  input: unknown;
  output: unknown;
}

interface Validation {
  isValidated: boolean;
  groundednessScore: number;
  hallucinatedSpans: Array<{ text: string; start: number; end: number }>;
}

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  validation?: Validation;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
  timestamp?: number;
}

export function ChatMessage({
  role,
  content,
  citations,
  validation,
  toolCalls,
  isStreaming,
  timestamp,
}: ChatMessageProps) {
  const isUser = role === "user";

  // Highlight hallucinated spans in content
  const highlightedContent =
    validation?.hallucinatedSpans && validation.hallucinatedSpans.length > 0
      ? highlightSpans(content, validation.hallucinatedSpans)
      : content;

  return (
    <div
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"} group`}
    >
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? "bg-blue-600" : "bg-purple-600"
        }`}
      >
        {isUser ? (
          <svg
            className="w-4 h-4 text-white"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
              clipRule="evenodd"
            />
          </svg>
        ) : (
          <svg
            className="w-4 h-4 text-white"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
        )}
      </div>

      {/* Content */}
      <div
        className={`flex-1 max-w-[80%] ${isUser ? "items-end" : "items-start"}`}
      >
        {/* Message bubble */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? "bg-blue-600 text-white rounded-tr-none"
              : "bg-gray-800 text-gray-100 rounded-tl-none"
          }`}
        >
          {isStreaming ? (
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                <span
                  className="w-2 h-2 bg-current rounded-full animate-bounce"
                  style={{ animationDelay: "0ms" }}
                />
                <span
                  className="w-2 h-2 bg-current rounded-full animate-bounce"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="w-2 h-2 bg-current rounded-full animate-bounce"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
              <span className="text-sm opacity-75">Thinking...</span>
            </div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {highlightedContent}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Assistant extras (not streaming) */}
        {!isUser && !isStreaming && (
          <div className="mt-2 space-y-2">
            {/* Validation badge */}
            {validation && (
              <ValidationBadge
                groundednessScore={validation.groundednessScore}
                isValidated={validation.isValidated}
              />
            )}

            {/* Citations */}
            {citations && citations.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Sources ({citations.length})
                </h4>
                {citations.map((citation, i) => (
                  <CitationCard key={i} citation={citation} index={i} />
                ))}
              </div>
            )}

            {/* Tool calls */}
            {toolCalls && toolCalls.length > 0 && (
              <ToolCallPanel toolCalls={toolCalls} />
            )}
          </div>
        )}

        {/* Timestamp */}
        {timestamp && (
          <div
            className={`mt-1 text-xs text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity ${
              isUser ? "text-right" : "text-left"
            }`}
          >
            {new Date(timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// Helper to highlight hallucinated spans
function highlightSpans(
  content: string,
  spans: Array<{ text: string; start: number; end: number }>
): string {
  // Sort spans by start position in reverse order to avoid index shifting
  const sortedSpans = [...spans].sort((a, b) => b.start - a.start);

  let result = content;
  for (const span of sortedSpans) {
    // Wrap span in special markers (will be rendered as warning style)
    const before = result.slice(0, span.start);
    const spanText = result.slice(span.start, span.end);
    const after = result.slice(span.end);
    result = `${before}**⚠️ ${spanText}**${after}`;
  }

  return result;
}
