import { useState, useCallback } from "react";
import { useQuery, useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";

export interface Citation {
  paperId: string;
  paperTitle: string;
  relevantText: string;
  groundedness: number;
}

export interface ToolCall {
  toolName: string;
  input: unknown;
  output: unknown;
}

export interface ChatMessage {
  _id: Id<"chatMessages">;
  threadId: Id<"chatThreads">;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  validation?: {
    isValidated: boolean;
    groundednessScore: number;
    hallucinatedSpans: Array<{ text: string; start: number; end: number }>;
  };
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
  createdAt: number;
}

interface UseStreamingChatOptions {
  sessionId: Id<"sessions">;
  threadId?: Id<"chatThreads">;
}

export function useStreamingChat({ sessionId, threadId }: UseStreamingChatOptions) {
  const [currentThreadId, setCurrentThreadId] = useState<Id<"chatThreads"> | null>(
    threadId ?? null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get messages for current thread
  const messages = useQuery(
    api.chat.messages.listForThread,
    currentThreadId ? { threadId: currentThreadId } : "skip"
  ) as ChatMessage[] | undefined;

  // Get threads for session
  const threads = useQuery(api.chat.threads.listForSession, { sessionId });

  // Actions
  const sendMessageAction = useAction(api.chat.actions.sendMessage);
  const startThreadAction = useAction(api.chat.actions.startThread);

  // Send a message
  const sendMessage = useCallback(
    async (message: string) => {
      setIsLoading(true);
      setError(null);

      try {
        if (currentThreadId) {
          // Continue existing thread
          await sendMessageAction({
            threadId: currentThreadId,
            sessionId,
            message,
          });
        } else {
          // Start new thread
          const result = await startThreadAction({
            sessionId,
            message,
          });
          setCurrentThreadId(result.threadId);
        }
      } catch (err) {
        console.error("[useStreamingChat] Error sending message:", err);
        setError(err instanceof Error ? err.message : "Failed to send message");
      } finally {
        setIsLoading(false);
      }
    },
    [currentThreadId, sessionId, sendMessageAction, startThreadAction]
  );

  // Start a new thread (just clears the current thread - actual creation happens on first message)
  const startNewThread = useCallback(
    async () => {
      // Don't create the thread directly - let sendMessage handle it
      // This ensures the agent thread is properly created via startThreadAction
      setCurrentThreadId(null);
      setError(null);
      return null;
    },
    []
  );

  // Select an existing thread
  const selectThread = useCallback((threadId: Id<"chatThreads">) => {
    setCurrentThreadId(threadId);
    setError(null);
  }, []);

  return {
    messages: messages ?? [],
    threads: threads ?? [],
    currentThreadId,
    isLoading,
    error,
    sendMessage,
    startNewThread,
    selectThread,
  };
}
