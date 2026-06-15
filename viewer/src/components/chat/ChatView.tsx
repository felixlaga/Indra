import { ChatInterface } from "./ChatInterface";
import type { Id } from "../../../convex/_generated/dataModel";

interface ChatViewProps {
  sessionId: Id<"sessions">;
  sessionQuery?: string;
  onBack: () => void;
  onSwitchToGraph: () => void;
}

export function ChatView({
  sessionId,
  sessionQuery,
  onBack,
  onSwitchToGraph,
}: ChatViewProps) {
  return (
    <div className="relative h-screen">
      {/* View toggle */}
      <div className="absolute top-4 right-4 z-10">
        <div className="flex bg-gray-800 rounded-lg p-1 border border-gray-700">
          <button
            onClick={onSwitchToGraph}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors rounded"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
            <span>Graph</span>
          </button>
          <button
            disabled
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-700 text-white rounded"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <span>Chat</span>
          </button>
        </div>
      </div>

      {/* Chat interface */}
      <ChatInterface
        sessionId={sessionId}
        sessionQuery={sessionQuery}
        onBack={onBack}
      />
    </div>
  );
}
