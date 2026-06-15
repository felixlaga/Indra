import { useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import { Id } from "../../convex/_generated/dataModel";

interface SessionListProps {
  onSelectSession: (id: Id<"sessions">) => void;
}

export function SessionList({ onSelectSession }: SessionListProps) {
  const sessions = useQuery(api.sessions.list);

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const statusColors: Record<string, string> = {
    running: "bg-cyan-500",
    completed: "bg-green-500",
    failed: "bg-red-500",
    pending: "bg-gray-500",
  };

  const statusBgColors: Record<string, string> = {
    running: "bg-cyan-900/30",
    completed: "bg-green-900/30",
    failed: "bg-red-900/30",
    pending: "bg-gray-900/30",
  };

  if (!sessions) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900">
        <div className="text-xl text-gray-400">Loading sessions...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-2">Research Sessions</h1>
        <p className="text-gray-400 mb-8">
          Select a session to view the research graph visualization
        </p>

        {sessions.length === 0 ? (
          <div className="bg-gray-800 rounded-lg p-8 text-center">
            <p className="text-gray-400 text-lg mb-2">No sessions yet</p>
            <p className="text-gray-500 text-sm">
              Run a research query to create a session:
            </p>
            <code className="block mt-4 bg-gray-900 text-green-400 p-3 rounded text-sm">
              uv run python run_research_live.py "your research query"
            </code>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((session) => (
              <button
                key={session._id}
                onClick={() => onSelectSession(session._id)}
                className={`w-full text-left p-4 rounded-lg border border-gray-700 hover:border-gray-600 transition-all ${statusBgColors[session.status]}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-medium text-white truncate">
                      {session.initialQuery}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      {formatDate(session.createdAt)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${statusColors[session.status]} ${session.status === "running" ? "animate-pulse" : ""}`}
                    />
                    <span
                      className={`text-sm capitalize ${
                        session.status === "running"
                          ? "text-cyan-400"
                          : session.status === "completed"
                            ? "text-green-400"
                            : session.status === "failed"
                              ? "text-red-400"
                              : "text-gray-400"
                      }`}
                    >
                      {session.status}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
