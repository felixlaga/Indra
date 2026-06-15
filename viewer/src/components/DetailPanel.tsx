import { useState } from "react";

interface NodeData {
  id: string;
  type: string;
  label: string;
  color: string;
  size: number;
  data: Record<string, unknown>;
}

interface DetailPanelProps {
  node: NodeData | null;
}

type PaperTab = "overview" | "abstract" | "summary";

function ProgressBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
      <div
        className="h-full progress-bar rounded-full"
        style={{
          width: `${Math.min(100, value * 100)}%`,
          backgroundColor: color,
        }}
      />
    </div>
  );
}

function PaperTabs({ abstract, summaryText }: { abstract?: string; summaryText?: string }) {
  const [activeTab, setActiveTab] = useState<PaperTab>(summaryText ? "summary" : "abstract");

  const tabs: { id: PaperTab; label: string; available: boolean }[] = [
    { id: "summary", label: "Summary", available: !!summaryText },
    { id: "abstract", label: "Abstract", available: !!abstract },
  ];

  const availableTabs = tabs.filter(t => t.available);

  if (availableTabs.length === 0) return null;

  return (
    <div className="mt-3 border-t border-gray-700 pt-3">
      {/* Tab Buttons */}
      <div className="flex gap-1 mb-2">
        {availableTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              activeTab === tab.id
                ? "bg-gray-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-gray-800 rounded-md p-3 max-h-48 overflow-y-auto">
        {activeTab === "summary" && summaryText && (
          <div>
            <p className="text-gray-300 text-sm leading-relaxed">{summaryText}</p>
            <p className="text-xs text-green-500 mt-2 flex items-center gap-1">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              HaluGate Validated
            </p>
          </div>
        )}
        {activeTab === "abstract" && abstract && (
          <p className="text-gray-300 text-sm leading-relaxed">{abstract}</p>
        )}
      </div>
    </div>
  );
}

export function DetailPanel({ node }: DetailPanelProps) {
  if (!node) {
    return (
      <div className="flex-1 p-4 border-b border-gray-700">
        <h3 className="text-lg font-semibold text-gray-400 mb-2">Details</h3>
        <p className="text-gray-500 text-sm">Click a node to see details</p>
      </div>
    );
  }

  const renderBranchDetails = () => {
    const data = node.data;
    return (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 uppercase">Query</label>
          <p className="text-gray-200 text-sm">{data.query as string}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 uppercase">Status</label>
            <p
              className={`text-sm font-medium ${
                data.status === "running"
                  ? "text-cyan-400"
                  : data.status === "completed"
                    ? "text-green-400"
                    : data.status === "paused"
                      ? "text-amber-400"
                      : "text-gray-400"
              }`}
            >
              {data.status as string}
            </p>
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Mode</label>
            <p className="text-gray-200 text-sm">{data.mode as string}</p>
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500 uppercase mb-1 block">
            Context Used ({((data.contextUtilization as number) * 100).toFixed(1)}%)
          </label>
          <ProgressBar value={data.contextUtilization as number} color="#60a5fa" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 uppercase">Papers</label>
            <p className="text-gray-200 text-lg font-semibold">
              {data.paperCount as number}
            </p>
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Summaries</label>
            <p className="text-gray-200 text-lg font-semibold">
              {data.summaryCount as number}
            </p>
          </div>
        </div>
      </div>
    );
  };

  const renderPaperDetails = () => {
    const data = node.data;
    const authors = data.authors as Array<{ name?: string }>;
    const abstract = data.abstract as string | undefined;
    const summaryText = data.summaryText as string | undefined;
    const iterationNumber = data.iterationNumber as number | undefined;

    return (
      <div className="space-y-3">
        {/* Iteration Badge */}
        {iterationNumber !== undefined && (
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-blue-900 text-blue-300 text-xs rounded-full">
              Iteration {iterationNumber}
            </span>
          </div>
        )}

        {/* Title */}
        <div>
          <label className="text-xs text-gray-500 uppercase">Title</label>
          <p className="text-gray-200 text-sm">{data.title as string}</p>
        </div>

        {/* Authors */}
        {authors && authors.length > 0 && (
          <div>
            <label className="text-xs text-gray-500 uppercase">Authors</label>
            <p className="text-gray-300 text-sm">
              {authors
                .slice(0, 3)
                .map((a) => a.name)
                .filter(Boolean)
                .join(", ")}
              {authors.length > 3 && ` +${authors.length - 3} more`}
            </p>
          </div>
        )}

        {/* Year, Citations, Venue Grid */}
        <div className="grid grid-cols-2 gap-3">
          {(data.year as number | undefined) && (
            <div>
              <label className="text-xs text-gray-500 uppercase">Year</label>
              <p className="text-gray-200 text-sm">{data.year as number}</p>
            </div>
          )}
          {(data.citationCount as number | undefined) !== undefined && (
            <div>
              <label className="text-xs text-gray-500 uppercase">Citations</label>
              <p className="text-gray-200 text-sm">{data.citationCount as number}</p>
            </div>
          )}
        </div>
        {(data.venue as string | undefined) && (
          <div>
            <label className="text-xs text-gray-500 uppercase">Venue</label>
            <p className="text-gray-300 text-sm">{data.venue as string}</p>
          </div>
        )}

        {/* Groundedness */}
        <div>
          <label className="text-xs text-gray-500 uppercase mb-1 block">
            Groundedness ({((data.groundedness as number) * 100).toFixed(0)}%)
          </label>
          <ProgressBar value={data.groundedness as number} color={node.color} />
        </div>

        {/* Tabs for Abstract / Summary */}
        {(abstract || summaryText) && (
          <PaperTabs abstract={abstract} summaryText={summaryText} />
        )}

        {/* Link to Semantic Scholar */}
        {(data.paperId as string | undefined) && (
          <a
            href={`https://www.semanticscholar.org/paper/${data.paperId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300 mt-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            View on Semantic Scholar
          </a>
        )}
      </div>
    );
  };

  const renderHypothesisDetails = () => {
    const data = node.data;
    const supportingPapers = data.supportingPaperIds as string[];
    const iterationNumber = data.iterationNumber as number | undefined;
    return (
      <div className="space-y-3">
        {/* Iteration Badge */}
        {iterationNumber !== undefined && (
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-purple-900 text-purple-300 text-xs rounded-full">
              Iteration {iterationNumber}
            </span>
          </div>
        )}
        <div>
          <label className="text-xs text-gray-500 uppercase">Hypothesis</label>
          <p className="text-gray-200 text-sm leading-relaxed">{data.text as string}</p>
        </div>
        <div>
          <label className="text-xs text-gray-500 uppercase mb-1 block">
            Confidence ({((data.confidence as number) * 100).toFixed(0)}%)
          </label>
          <ProgressBar value={data.confidence as number} color={node.color} />
        </div>
        <div>
          <label className="text-xs text-gray-500 uppercase">Supporting Papers</label>
          <p className="text-gray-200 text-lg font-semibold">
            {supportingPapers?.length ?? 0}
          </p>
        </div>
      </div>
    );
  };

  const typeLabels: Record<string, string> = {
    branch: "Branch",
    paper: "Paper",
    hypothesis: "Hypothesis",
  };

  return (
    <div className="flex-1 p-4 border-b border-gray-700 overflow-y-auto">
      <div className="flex items-center gap-2 mb-4">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: node.color }}
        />
        <h3 className="text-lg font-semibold text-white">
          {typeLabels[node.type]}
        </h3>
      </div>
      {node.type === "branch" && renderBranchDetails()}
      {node.type === "paper" && renderPaperDetails()}
      {node.type === "hypothesis" && renderHypothesisDetails()}
    </div>
  );
}
