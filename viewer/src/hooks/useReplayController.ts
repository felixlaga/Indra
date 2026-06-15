import { useState, useCallback, useRef, useEffect } from "react";

export interface ReplayState {
  isPlaying: boolean;
  playbackSpeed: number;
  currentTime: number;
  progress: number;
  startTime: number;
  endTime: number;
  duration: number;
}

export interface ReplayActions {
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  setSpeed: (speed: number) => void;
  seekTo: (time: number) => void;
  seekToProgress: (progress: number) => void;
  reset: () => void;
}

export interface UseReplayControllerResult {
  state: ReplayState;
  actions: ReplayActions;
}

interface UseReplayControllerProps {
  startTime: number;
  endTime: number;
  onTimeUpdate?: (time: number) => void;
}

export function useReplayController({
  startTime,
  endTime,
  onTimeUpdate,
}: UseReplayControllerProps): UseReplayControllerResult {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentTime, setCurrentTime] = useState(startTime);

  const lastFrameTimeRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  const duration = endTime - startTime;
  const progress = duration > 0 ? (currentTime - startTime) / duration : 0;

  // Animation loop using requestAnimationFrame
  const tick = useCallback(
    (timestamp: number) => {
      if (!lastFrameTimeRef.current) {
        lastFrameTimeRef.current = timestamp;
      }

      const deltaMs = timestamp - lastFrameTimeRef.current;
      lastFrameTimeRef.current = timestamp;

      // Calculate time advancement based on playback speed
      // Speed 1 = 1 second of events per 1 second real time
      // Speed 10 = 10 seconds of events per 1 second real time
      const timeAdvance = deltaMs * playbackSpeed;

      setCurrentTime((prev) => {
        const next = prev + timeAdvance;
        if (next >= endTime) {
          setIsPlaying(false);
          return endTime;
        }
        return next;
      });

      // This callback intentionally schedules the next animation frame.
      // eslint-disable-next-line react-hooks/immutability
      animationFrameRef.current = requestAnimationFrame(tick);
    },
    [playbackSpeed, endTime]
  );

  // Start/stop animation loop when isPlaying changes
  useEffect(() => {
    if (isPlaying) {
      lastFrameTimeRef.current = null;
      animationFrameRef.current = requestAnimationFrame(tick);
    } else {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, tick]);

  // Notify parent of time updates
  useEffect(() => {
    onTimeUpdate?.(currentTime);
  }, [currentTime, onTimeUpdate]);

  // Reset when start/end times change
  useEffect(() => {
    // Replay bounds come from graph data; local playback state must follow them.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCurrentTime(startTime);
    setIsPlaying(false);
  }, [startTime, endTime]);

  const play = useCallback(() => {
    // If at end, restart from beginning
    if (currentTime >= endTime) {
      setCurrentTime(startTime);
    }
    setIsPlaying(true);
  }, [currentTime, endTime, startTime]);

  const pause = useCallback(() => {
    setIsPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  }, [isPlaying, play, pause]);

  const setSpeed = useCallback((speed: number) => {
    setPlaybackSpeed(Math.max(0.5, Math.min(100, speed)));
  }, []);

  const seekTo = useCallback(
    (time: number) => {
      setCurrentTime(Math.max(startTime, Math.min(endTime, time)));
    },
    [startTime, endTime]
  );

  const seekToProgress = useCallback(
    (prog: number) => {
      const clampedProgress = Math.max(0, Math.min(1, prog));
      const time = startTime + clampedProgress * duration;
      setCurrentTime(time);
    },
    [startTime, duration]
  );

  const reset = useCallback(() => {
    setIsPlaying(false);
    setCurrentTime(startTime);
    setPlaybackSpeed(1);
  }, [startTime]);

  return {
    state: {
      isPlaying,
      playbackSpeed,
      currentTime,
      progress,
      startTime,
      endTime,
      duration,
    },
    actions: {
      play,
      pause,
      togglePlay,
      setSpeed,
      seekTo,
      seekToProgress,
      reset,
    },
  };
}
