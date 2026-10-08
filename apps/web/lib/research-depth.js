/**
 * Research depth presets sent as `parameters.research`. Each bounds papers,
 * Scout branches and model calls; the API validates every value again.
 *
 * @typedef {{ id: string, label: string, description: string, research: Record<string, number | boolean> }} DepthPreset
 */

/** @type {DepthPreset[]} */
export const DEPTH_PRESETS = [
  {
    id: "quick",
    label: "Quick",
    description: "One search and up to 5 papers. No follow-up branches.",
    research: { max_papers: 5, max_depth: 0, synthesize: false, max_model_calls: 30 },
  },
  {
    id: "standard",
    label: "Standard",
    description: "Up to 3 follow-up branches and a cross-paper synthesis.",
    research: {
      max_papers: 5,
      max_depth: 1,
      max_branches: 3,
      branch_papers: 3,
      synthesize: true,
      max_model_calls: 45,
    },
  },
  {
    id: "deep",
    label: "Deep",
    description: "Two levels of follow-ups, up to 8 branches.",
    research: {
      max_papers: 6,
      max_depth: 2,
      max_branches: 8,
      branch_papers: 3,
      synthesize: true,
      max_model_calls: 100,
    },
  },
];

export const DEFAULT_DEPTH = "standard";

/** @param {string} id */
export function depthPreset(id) {
  return DEPTH_PRESETS.find((preset) => preset.id === id) ?? DEPTH_PRESETS[1];
}

/**
 * Upper bound on papers a preset can read, for the form's plain-language hint.
 * @param {DepthPreset} preset
 */
export function maxPapers(preset) {
  const r = preset.research;
  const scouting = Number(r.max_depth) > 0 && Number(r.max_branches) > 0;
  return Number(r.max_papers) + (scouting ? Number(r.max_branches) * Number(r.branch_papers) : 0);
}
