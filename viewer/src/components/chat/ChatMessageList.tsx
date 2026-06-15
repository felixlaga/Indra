import { useRef, useEffect } from "react";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessage as ChatMessageType } from "../../hooks/useStreamingChat";

interface ChatMessageListProps {
  messages: ChatMessageType[];
  isLoading?: boolean;
}

export function ChatMessageList({ messages, isLoading }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 p-8">
        <svg
          className="w-16 h-16 mb-4 opacity-30"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
        <h3 className="text-lg font-medium text-gray-300 mb-2">
          Start a conversation
        </h3>
        <p className="text-sm text-center max-w-md">
          Ask questions about the research papers, hypotheses, or findings from
          this session. The AI will cite sources and validate responses.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {messages.map((message) => (
        <ChatMessage
          key={message._id}
          role={message.role}
          content={message.content}
          citations={message.citations}
          validation={message.validation}
          toolCalls={message.toolCalls}
          isStreaming={message.isStreaming}
          timestamp={message.createdAt}
        />
      ))}

      {/* Loading indicator */}
      {isLoading && messages.every((m) => !m.isStreaming) && (
        <ChatMessage
          role="assistant"
          content=""
          isStreaming={true}
        />
      )}

      {/* Scroll anchor */}
      <div ref={bottomRef} />
    </div>
  );
}
