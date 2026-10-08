import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_DEPTH, DEPTH_PRESETS, depthPreset, maxPapers } from "../lib/research-depth.js";

test("depth presets stay within the API's research limits", () => {
  for (const { research } of DEPTH_PRESETS) {
    assert.ok(research.max_papers >= 1 && research.max_papers <= 20);
    assert.ok(research.max_depth >= 0 && research.max_depth <= 3);
    assert.ok((research.max_branches ?? 0) <= 12);
    assert.ok(research.max_model_calls >= 1 && research.max_model_calls <= 100);
  }
});

test("quick disables Scouts and synthesis; standard is the default", () => {
  assert.equal(DEFAULT_DEPTH, "standard");
  const quick = depthPreset("quick").research;
  assert.equal(quick.max_depth, 0);
  assert.equal(quick.synthesize, false);
  assert.equal(depthPreset("unknown").id, "standard");
});

test("maxPapers counts Scout branches only when scouting is on", () => {
  assert.equal(maxPapers(depthPreset("quick")), 5);
  assert.equal(maxPapers(depthPreset("standard")), 5 + 3 * 3);
  assert.equal(maxPapers(depthPreset("deep")), 6 + 8 * 3);
});
