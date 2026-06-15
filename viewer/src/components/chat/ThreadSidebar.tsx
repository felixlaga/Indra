import type { Id } from "../../../convex/_generated/dataModel";

interface Thread {
  _id: Id<"chatThreads">;
  sessionId: Id<"sessions">;
  title?: string;
  createdAt: number;
  updatedAt: number;
}

interface ThreadSidebarProps {
  threads: Thread[];
  currentThreadId: Id<"chatThreads"> | null;
  onSelectThread: (threadId: Id<"chatThreads">) => void;
  onNewThread: () => void;
}

export function ThreadSidebar({
  threads,
  currentThreadId,
  onSelectThread,
  onNewThread,
}: ThreadSidebarProps) {
  return (
    <div className="w-64 bg-gray-900 border-r border-gray-700 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-sm font-medium text-gray-300 uppercase tracking-wider">
          Chat Threads
        </h2>
      </div>

      {/* New thread button */}
      <div className="p-3">
        <button
          onClick={onNewThread}
          className="w-full flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
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
              d="M12 4v16m8-8H4"
            />
          </svg>
          <span className="text-sm font-medium">New Thread</span>
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {threads.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            No threads yet
          </div>
        ) : (
          threads.map((thread) => (
            <button
              key={thread._id}
              onClick={() => onSelectThread(thread._id)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                currentThreadId === thread._id
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
              }`}
            >
              <div className="truncate text-sm font-medium">
                {thread.title || "Untitled thread"}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                {formatRelativeTime(thread.updatedAt)}
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}
