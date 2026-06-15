import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { ResearchGraph } from "./components/ResearchGraph";
import { ChatView } from "./components/chat";
import { DashboardShell } from "./components/dashboard/DashboardShell";

type ViewMode = "dashboard" | "graph" | "chat";

function App() {
  const [selectedSessionId, setSelectedSessionId] = useState<Id<"sessions"> | null>(
    null
  );
  const [viewMode, setViewMode] = useState<ViewMode>("dashboard");

  // Get session details for the chat view
  const session = useQuery(
    api.sessions.getById,
    selectedSessionId ? { id: selectedSessionId } : "skip"
  );

  const handleSelectSession = (sessionId: Id<"sessions">) => {
    setSelectedSessionId(sessionId);
    setViewMode("graph"); // Default to graph view
  };

  const handleBack = () => {
    setViewMode("dashboard");
  };

  // Show dashboard shell
  if (!selectedSessionId || viewMode === "dashboard") {
    return <DashboardShell onOpenSessionGraph={handleSelectSession} />;
  }

  // Show graph view
  if (viewMode === "graph") {
    return (
      <div className="relative h-screen">
        {/* View toggle */}
        <div className="absolute top-4 right-4 z-10">
          <div className="flex bg-gray-800 rounded-lg p-1 border border-gray-700">
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
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              <span>Graph</span>
            </button>
            <button
              onClick={() => setViewMode("chat")}
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
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              <span>Chat</span>
            </button>
          </div>
        </div>

        <ResearchGraph sessionId={selectedSessionId} onBack={handleBack} />
      </div>
    );
  }

  // Show chat view
  if (viewMode === "chat") {
    return (
      <ChatView
        sessionId={selectedSessionId}
        sessionQuery={session?.initialQuery}
        onBack={handleBack}
        onSwitchToGraph={() => setViewMode("graph")}
      />
    );
  }

  return null;
}

export default App;
