"use client";

import { useEffect, useRef, useState } from "react";

import { erlaApi } from "@/lib/api";
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

    async function connect() {
      try {
        const response = await fetch(
          `${erlaApi.baseUrl}/sessions/${sessionId}/events/stream?replay=false`,
          {
            headers: { Accept: "text/event-stream" },
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
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let boundary = buffer.indexOf("\n\n");
          while (boundary >= 0) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const event = parseFrame(frame);
            if (event) callbackRef.current(event);
            boundary = buffer.indexOf("\n\n");
          }
        }
      } catch (error) {
        if (controller.signal.aborted || cancelled) return;
        const message = error instanceof Error ? error.message : "Event stream disconnected";
        setState({ connected: false, error: message });
      }
    }

    void connect();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [sessionId]);

  return state;
}
