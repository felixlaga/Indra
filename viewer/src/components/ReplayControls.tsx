import { useCallback } from "react";
import { ReplayState, ReplayActions } from "../hooks/useReplayController";

interface ReplayControlsProps {
  state: ReplayState;
  actions: ReplayActions;
  isReplayMode: boolean;
  onToggleReplayMode: () => void;
  disabled?: boolean;
}

export function ReplayControls({
  state,
  actions,
  isReplayMode,
  onToggleReplayMode,
  disabled = false,
}: ReplayControlsProps) {
  const formatTime = useCallback((timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }, []);

  const formatDuration = useCallback((ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  }, []);

  const handleSeekbarChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const progress = parseFloat(e.target.value) / 100;
      actions.seekToProgress(progress);
    },
    [actions]
  );

  const handleSpeedChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      actions.setSpeed(parseFloat(e.target.value));
    },
    [actions]
  );

  return (
    <div className="bg-gray-800 border-t border-gray-700 p-4">
      {/* Mode Toggle */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Playback
        </h3>
        <button
          onClick={onToggleReplayMode}
          disabled={disabled}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            isReplayMode
              ? "bg-purple-600 text-white hover:bg-purple-700"
              : "bg-gray-700 text-gray-300 hover:bg-gray-600"
          } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          {isReplayMode ? "Replay Mode" : "Live Mode"}
        </button>
      </div>

      {isReplayMode && (
        <>
          {/* Timeline / Seekbar */}
          <div className="mb-4">
            <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
              <span>{formatTime(state.startTime)}</span>
              <span className="text-gray-300 font-medium">
                {formatTime(state.currentTime)}
              </span>
              <span>{formatTime(state.endTime)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={state.progress * 100}
              onChange={handleSeekbarChange}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer
                         [&::-webkit-slider-thumb]:appearance-none
                         [&::-webkit-slider-thumb]:w-4
                         [&::-webkit-slider-thumb]:h-4
                         [&::-webkit-slider-thumb]:rounded-full
                         [&::-webkit-slider-thumb]:bg-purple-500
                         [&::-webkit-slider-thumb]:hover:bg-purple-400
                         [&::-webkit-slider-thumb]:transition-colors"
            />
            <div className="flex items-center justify-between text-xs text-gray-500 mt-1">
              <span>Duration: {formatDuration(state.duration)}</span>
              <span>{Math.round(state.progress * 100)}%</span>
            </div>
          </div>

          {/* Playback Controls */}
          <div className="flex items-center gap-4">
            {/* Play/Pause Button */}
            <button
              onClick={actions.togglePlay}
              className="w-10 h-10 rounded-full bg-purple-600 hover:bg-purple-500
                         flex items-center justify-center transition-colors"
            >
              {state.isPlaying ? (
                <svg
                  className="w-5 h-5 text-white"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <rect x="6" y="4" width="4" height="16" />
                  <rect x="14" y="4" width="4" height="16" />
                </svg>
              ) : (
                <svg
                  className="w-5 h-5 text-white ml-0.5"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <polygon points="5,3 19,12 5,21" />
                </svg>
              )}
            </button>

            {/* Reset Button */}
            <button
              onClick={actions.reset}
              className="p-2 rounded-full text-gray-400 hover:text-white
                         hover:bg-gray-700 transition-colors"
              title="Reset"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>

            {/* Speed Control */}
            <div className="flex-1 flex items-center gap-2">
              <span className="text-xs text-gray-400 w-10">{state.playbackSpeed}x</span>
              <input
                type="range"
                min="1"
                max="100"
                step="1"
                value={state.playbackSpeed}
                onChange={handleSpeedChange}
                className="flex-1 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer
                           [&::-webkit-slider-thumb]:appearance-none
                           [&::-webkit-slider-thumb]:w-3
                           [&::-webkit-slider-thumb]:h-3
                           [&::-webkit-slider-thumb]:rounded-full
                           [&::-webkit-slider-thumb]:bg-gray-400
                           [&::-webkit-slider-thumb]:hover:bg-gray-300"
              />
              <span className="text-xs text-gray-500">Speed</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
