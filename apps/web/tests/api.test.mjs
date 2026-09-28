import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Exercise the real TypeScript client without a browser or a second test runner.
const source = await readFile(new URL("../lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
let moduleNumber = 0;
async function loadApi(key = "local-test-key") {
  const previous = { ...process.env };
  process.env.NEXT_PUBLIC_INDRA_API_URL = "http://localhost:8017/";
  process.env.NEXT_PUBLIC_INDRA_API_KEY = key;
  try {
    return await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}#${moduleNumber++}`);
  } finally {
    for (const name of ["NEXT_PUBLIC_INDRA_API_URL", "NEXT_PUBLIC_INDRA_API_KEY"]) {
      if (previous[name] === undefined) delete process.env[name];
      else process.env[name] = previous[name];
    }
  }
}

test("advisor and export catalog use the shared authenticated client", async (t) => {
  const { indraApi } = await loadApi("  local-test-key  ");
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    calls.push({ url, init });
    return Response.json({ ok: true });
  });
  await indraApi.getResearchAdvice("session-1");
  await indraApi.getExportCatalog("session-1");
  assert.deepEqual(calls.map(({ url }) => url), [
    "http://localhost:8017/sessions/session-1/analysis",
    "http://localhost:8017/sessions/session-1/exports",
  ]);
  for (const { init } of calls) {
    assert.equal(new Headers(init.headers).get("X-Indra-API-Key"), "local-test-key");
    assert.equal(init.cache, "no-store");
  }
});

test("downloads and event streams encode the key; local mode omits it", async (t) => {
  const api = await loadApi("key+with&symbols?");
  for (const raw of [api.exportDownloadUrl("s1", "bibtex"), api.indraUrlWithApiKey("/sessions/s1/events/stream")]) {
    assert.equal(new URL(raw).searchParams.get("api_key"), "key+with&symbols?");
  }
  const local = await loadApi("");
  assert.deepEqual(local.indraAuthHeaders(), {});
  assert.equal(new URL(local.exportDownloadUrl("s1", "bibtex")).search, "");
});

for (const [name, body, status, message] of [
  ["JSON rejection", '{"detail":"A valid Indra API key is required."}', 401, "A valid Indra API key is required."],
  ["plain-text gateway failure", "Bad Gateway", 502, "Indra API request failed with status 502"],
  ["empty service failure", "", 503, "Indra API request failed with status 503"],
]) {
  test(`API preserves status and useful error details for ${name}`, async (t) => {
    const { indraApi, ApiError } = await loadApi();
    t.mock.method(globalThis, "fetch", async () => new Response(body, { status }));
    await assert.rejects(indraApi.getResearchAdvice("s1"), (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, status);
      assert.equal(error.message, message);
      if (status !== 401) assert.equal(error.detail, body);
      return true;
    });
  });
}
