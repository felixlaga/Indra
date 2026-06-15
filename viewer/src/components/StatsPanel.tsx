interface StatsPanelProps {
  stats: {
    branchCount: number;
    paperCount: number;
    summaryCount: number;
    hypothesisCount: number;
  };
  session?: {
    parameters?: {
      profile?: string;
      max_iterations?: number;
      start_date?: string;
      end_date?: string;
      use_managing_agent?: boolean;
    };
  };
}

export function StatsPanel({ stats, session }: StatsPanelProps) {
  return (
    <div className="flex-1 p-4 space-y-4 overflow-y-auto">
      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Statistics
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-800 rounded-lg p-3">
            <p className="text-2xl font-bold text-blue-400">{stats.branchCount}</p>
            <p className="text-xs text-gray-500">Branches</p>
          </div>
          <div className="bg-gray-800 rounded-lg p-3">
            <p className="text-2xl font-bold text-green-400">{stats.paperCount}</p>
            <p className="text-xs text-gray-500">Papers</p>
          </div>
          <div className="bg-gray-800 rounded-lg p-3">
            <p className="text-2xl font-bold text-emerald-400">
              {stats.summaryCount}
            </p>
            <p className="text-xs text-gray-500">Summaries</p>
          </div>
          <div className="bg-gray-800 rounded-lg p-3">
            <p className="text-2xl font-bold text-purple-400">
              {stats.hypothesisCount}
            </p>
            <p className="text-xs text-gray-500">Hypotheses</p>
          </div>
        </div>
      </div>

      {/* Configuration section */}
      {session?.parameters && (
        <div>
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Configuration
          </h3>
          <div className="space-y-2 bg-gray-800 rounded-lg p-3">
            {session.parameters.profile && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Profile:</span>
                <span className="text-gray-300 font-medium">
                  {session.parameters.profile}
                </span>
              </div>
            )}
            {session.parameters.max_iterations && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Max Iterations:</span>
                <span className="text-gray-300 font-medium">
                  {session.parameters.max_iterations}
                </span>
              </div>
            )}
            {(session.parameters.start_date || session.parameters.end_date) && (
              <div className="flex flex-col gap-1 text-xs">
                <span className="text-gray-500">Date Range:</span>
                <span className="text-gray-300 font-medium">
                  {session.parameters.start_date || "—"} to{" "}
                  {session.parameters.end_date || "present"}
                </span>
              </div>
            )}
            {session.parameters.use_managing_agent !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Managing Agent:</span>
                <span className="text-gray-300 font-medium">
                  {session.parameters.use_managing_agent ? "Enabled" : "Disabled"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Legend
        </h3>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-cyan-400" />
            <span className="text-sm text-gray-300">Running Branch</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-green-500" />
            <span className="text-sm text-gray-300">Completed / High Groundedness</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-yellow-500" />
            <span className="text-sm text-gray-300">Medium Groundedness</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-red-500" />
            <span className="text-sm text-gray-300">Low Groundedness / Pruned</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-purple-500" />
            <span className="text-sm text-gray-300">Hypothesis</span>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Edge Types
        </h3>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-blue-400" />
            <span className="text-sm text-gray-300">Branch Split</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-green-400" />
            <span className="text-sm text-gray-300">Paper in Branch</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-purple-400" />
            <span className="text-sm text-gray-300">Hypothesis Link</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 bg-pink-400" />
            <span className="text-sm text-gray-300">Supporting Paper</span>
          </div>
        </div>
      </div>
    </div>
  );
}
