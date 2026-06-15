import { useCallback } from "react";
import { useStreamingChat } from "../../hooks/useStreamingChat";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";
import { ThreadSidebar } from "./ThreadSidebar";
import type { Id } from "../../../convex/_generated/dataModel";

interface ChatInterfaceProps {
  sessionId: Id<"sessions">;
  onBack: () => void;
  sessionQuery?: string;
}

export function ChatInterface({
  sessionId,
  onBack,
  sessionQuery,
}: ChatInterfaceProps) {
  const {
    messages,
    threads,
    currentThreadId,
    isLoading,
    error,
    sendMessage,
    startNewThread,
    selectThread,
  } = useStreamingChat({ sessionId });

  const handleNewThread = useCallback(() => {
    startNewThread();
  }, [startNewThread]);

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Thread sidebar */}
      <ThreadSidebar
        threads={threads}
        currentThreadId={currentThreadId}
        onSelectThread={selectThread}
        onNewThread={handleNewThread}
      />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="h-16 border-b border-gray-700 flex items-center justify-between px-6 bg-gray-900/80 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
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
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
              <span>Back</span>
            </button>

            <div className="h-6 w-px bg-gray-700" />

            <div>
              <h1 className="text-lg font-semibold text-white">Research Chat</h1>
              {sessionQuery && (
                <p className="text-xs text-gray-400 truncate max-w-md">
                  {sessionQuery}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* HaluGate indicator */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-green-900/30 border border-green-700/50 rounded-full">
              <svg
                className="w-3.5 h-3.5 text-green-400"
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
              <span className="text-xs font-medium text-green-400">
                HaluGate Enabled
              </span>
            </div>
          </div>
        </div>

        {/* Error display */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-400 text-sm">
            <span className="font-medium">Error:</span> {error}
          </div>
        )}

        {/* Message list */}
        <ChatMessageList messages={messages} isLoading={isLoading} />

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          isLoading={isLoading}
          placeholder={
            currentThreadId
              ? "Continue the conversation..."
              : "Start a new conversation about the research..."
          }
        />
      </div>
    </div>
  );
}
