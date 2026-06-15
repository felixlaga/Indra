import { useEffect, useRef, useMemo } from "react";
import { useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import { Id } from "../../convex/_generated/dataModel";

interface EventFeedProps {
  sessionId: Id<"sessions">;
  replayTime?: number;
}

const eventIcons: Record<string, string> = {
  session_started: "🚀",
  branch_created: "🌿",
  branch_status_changed: "📊",
  papers_added: "📄",
  summary_validated: "✅",
  hypothesis_created: "💡",
  session_completed: "🏁",
  error: "❌",
};

const eventColors: Record<string, string> = {
  session_started: "text-blue-400",
  branch_created: "text-green-400",
  branch_status_changed: "text-yellow-400",
  papers_added: "text-cyan-400",
  summary_validated: "text-emerald-400",
  hypothesis_created: "text-purple-400",
  session_completed: "text-green-400",
  error: "text-red-400",
};

export function EventFeed({ sessionId, replayTime }: EventFeedProps) {
  const events = useQuery(api.events.subscribe, { sessionId });
  const scrollRef = useRef<HTMLDivElement>(null);

  // Filter events based on replay time
  const visibleEvents = useMemo(() => {
    if (!events) return [];
    if (replayTime === undefined) return events;

    return events.filter((event) => event.createdAt <= replayTime);
  }, [events, replayTime]);

  // Find the most recent event for highlighting
  const mostRecentEventId = useMemo(() => {
    if (!visibleEvents || visibleEvents.length === 0) return null;
    return visibleEvents[visibleEvents.length - 1]._id;
  }, [visibleEvents]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visibleEvents]);

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const formatEventMessage = (event: {
    eventType: string;
    payload: Record<string, unknown>;
  }) => {
    const { eventType, payload } = event;
    switch (eventType) {
      case "session_started":
        return `Session started: ${payload.query}`;
      case "branch_created":
        return `New branch: ${(payload.query as string)?.slice(0, 40)}...`;
      case "branch_status_changed":
        return `Branch ${(payload.branchId as string)?.slice(0, 8)}: ${payload.status ?? "updated"}`;
      case "papers_added":
        return `Added ${payload.count} papers`;
      case "summary_validated":
        return `Validated: "${(payload.paperTitle as string)?.slice(0, 30)}..." (${((payload.groundedness as number) * 100).toFixed(0)}%)`;
      case "hypothesis_created":
        return `Hypothesis: "${(payload.text as string)?.slice(0, 40)}..."`;
      case "session_completed":
        return "Session completed";
      case "error":
        return `Error: ${payload.message}`;
      default:
        return eventType;
    }
  };

  if (!events) {
    return (
      <div className="h-64 p-4">
        <h3 className="text-lg font-semibold text-gray-400 mb-2">Events</h3>
        <p className="text-gray-500 text-sm">Loading events...</p>
      </div>
    );
  }

  const isReplayMode = replayTime !== undefined;

  return (
    <div className="h-64 flex flex-col">
      <div className="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          {isReplayMode ? "Events (Replay)" : "Live Events"} ({visibleEvents.length})
        </h3>
        {isReplayMode && (
          <span className="text-xs text-purple-400">
            {formatTime(replayTime)}
          </span>
        )}
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-2 space-y-1"
      >
        {visibleEvents.length === 0 ? (
          <p className="text-gray-500 text-sm p-2">No events yet</p>
        ) : (
          visibleEvents.map((event) => (
            <div
              key={event._id}
              className={`flex items-start gap-2 p-2 rounded transition-colors ${
                isReplayMode && event._id === mostRecentEventId
                  ? "bg-purple-900/30 border border-purple-700"
                  : "hover:bg-gray-800"
              }`}
            >
              <span className="text-lg">
                {eventIcons[event.eventType] || "📌"}
              </span>
              <div className="flex-1 min-w-0">
                <p
                  className={`text-sm ${eventColors[event.eventType] || "text-gray-300"}`}
                >
                  {formatEventMessage(event)}
                </p>
                <p className="text-xs text-gray-500">
                  {formatTime(event.createdAt)}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
