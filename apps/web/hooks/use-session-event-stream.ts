"use client";

import { useEffect, useRef, useState } from "react";

import { indraAuthHeaders, indraUrlWithApiKey } from "@/lib/api";
import type { EventRecord } from "@/lib/types";

interface StreamState {
  connected: boolean;
  error: string | null;
}

function parseFrame(frame: string): EventRecord | null {
  const data = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  try {
    return JSON.parse(data) as EventRecord;
  } catch {
    return null;
  }
}

export function useSessionEventStream(
  sessionId: string,
  onEvent: (event: EventRecord) => void,
): StreamState {
  const callbackRef = useRef(onEvent);
  const [state, setState] = useState<StreamState>({
    connected: false,
    error: null,
  });

  useEffect(() => {
    callbackRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    let cursor: string | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    async function connect() {
      try {
        const response = await fetch(
          indraUrlWithApiKey(`/sessions/${sessionId}/events/stream?${cursor ? `cursor=${encodeURIComponent(cursor)}` : "replay=true"}`),
          {
            headers: { Accept: "text/event-stream", ...indraAuthHeaders() },
            cache: "no-store",
            signal: controller.signal,
          },
        );
        if (!response.ok || !response.body) {
          throw new Error(`Event stream failed with status ${response.status}`);
        }
        if (!cancelled) setState({ connected: true, error: null });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) throw new Error("Event stream closed; reconnecting");
          buffer += decoder.decode(value, { stream: true });
          let boundary = buffer.indexOf("\n\n");
          while (boundary >= 0) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const event = parseFrame(frame);
            if (event) {
              cursor = event.id;
              callbackRef.current(event);
            }
            boundary = buffer.indexOf("\n\n");
          }
        }
      } catch (error) {
        if (controller.signal.aborted || cancelled) return;
        const message = error instanceof Error ? error.message : "Event stream disconnected";
        setState({ connected: false, error: message });
        retryTimer = setTimeout(() => void connect(), 2000);
      }
    }

    void connect();
    return () => {
      cancelled = true;
      controller.abort();
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [sessionId]);

  return state;
}
