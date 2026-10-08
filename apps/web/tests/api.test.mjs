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

test("the browser client calls this app's same-origin proxy without keys", async (t) => {
  const { indraApi } = await loadApi("  local-test-key  ");
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    calls.push({ url, init });
    return Response.json({ ok: true });
  });
  await indraApi.getResearchAdvice("session-1");
  await indraApi.getExportCatalog("session-1");
  assert.deepEqual(calls.map(({ url }) => url), [
    "/api/indra/sessions/session-1/analysis",
    "/api/indra/sessions/session-1/exports",
  ]);
  for (const { init } of calls) {
    const headers = new Headers(init.headers);
    assert.equal(headers.get("X-Indra-API-Key"), null);
    assert.equal(headers.get("Authorization"), null);
    assert.equal(init.cache, "no-store");
  }
});

test("downloads use same-origin links that carry no key", async () => {
  const api = await loadApi("key+with&symbols?");
  assert.equal(api.exportDownloadUrl("s1", "bibtex"), "/api/indra/sessions/s1/exports/bibtex");
  assert.equal(api.indraUrl("/sessions/s1/events/stream"), "/api/indra/sessions/s1/events/stream");
});

test("an accounts-mode 401 sends the user to sign in and keeps their place", async (t) => {
  const { indraApi } = await loadApi();
  const assigned = [];
  globalThis.window = { location: { pathname: "/sessions/s1", search: "?view=graph", assign: (url) => assigned.push(url) } };
  t.after(() => delete globalThis.window);
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ detail: "Sign in to use Indra.", mode: "accounts" }, { status: 401 }));
  await assert.rejects(indraApi.listProjects(), /Sign in to use Indra/);
  assert.deepEqual(assigned, ["/login?next=%2Fsessions%2Fs1%3Fview%3Dgraph"]);
});

const upstreamSource = await readFile(new URL("../lib/server/upstream.ts", import.meta.url), "utf8");
const upstreamModule = ts.transpileModule(upstreamSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;

test("the server proxy sends the key as a proxy key and the token as a bearer", async () => {
  process.env.INDRA_API_KEY = " server-key ";
  process.env.INDRA_API_URL = "http://api.internal:8000/";
  try {
    const upstream = await import(`data:text/javascript;base64,${Buffer.from(upstreamModule).toString("base64")}#u${moduleNumber++}`);
    const headers = upstream.upstreamHeaders("user-token");
    assert.equal(headers.get("X-Indra-Proxy-Key"), "server-key");
    assert.equal(headers.get("X-Indra-API-Key"), null);
    assert.equal(headers.get("Authorization"), "Bearer user-token");
    assert.equal(upstream.upstreamHeaders().get("Authorization"), null);
    assert.equal(upstream.upstreamUrl("/projects"), "http://api.internal:8000/projects");
    const cookie = upstream.sessionCookie("t", new Date(0), true);
    assert.equal(cookie.httpOnly, true);
    assert.equal(cookie.sameSite, "lax");
  } finally {
    delete process.env.INDRA_API_KEY;
    delete process.env.INDRA_API_URL;
  }
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

test("research views poll queued responses and return only completed data", async (t) => {
  const { indraApi } = await loadApi();
  const realTimer = globalThis.setTimeout;
  t.mock.method(globalThis, "setTimeout", (fn) => realTimer(fn, 0));
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => ++calls < 3
    ? Response.json({ status: "queued", detail: "Preparing" }, { status: 202 })
    : Response.json({ nodes: [{ paper_id: "p1" }] }));
  assert.deepEqual(await indraApi.getResearchMap("s1"), { nodes: [{ paper_id: "p1" }] });
  assert.equal(calls, 3);
});

test("research view polling stops on navigation abort", async (t) => {
  const { indraApi } = await loadApi();
  const controller = new AbortController();
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => {
    calls++;
    controller.abort(new Error("Navigation"));
    return Response.json({ status: "queued" }, { status: 202 });
  });
  await assert.rejects(indraApi.getResearchMap("s1", controller.signal), /Navigation/);
  assert.equal(calls, 1);
});

test("research view wait has a finite timeout with actionable queue details", async (t) => {
  const { indraApi } = await loadApi();
  const realTimer = globalThis.setTimeout;
  t.mock.method(globalThis, "setTimeout", (fn) => realTimer(fn, 0));
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => {
    calls++;
    return Response.json({ status: "queued", detail: "Start the view worker." }, { status: 202 });
  });
  await assert.rejects(indraApi.getResearchAdvice("s1"), /Start the view worker/);
  assert.equal(calls, 61);
});

test("the session hub asks for the compact snapshot", async (t) => {
  const { indraApi } = await loadApi();
  const urls = [];
  t.mock.method(globalThis, "fetch", async (url) => {
    urls.push(url);
    return Response.json({ events: [] });
  });
  await indraApi.getSessionSnapshot("s1");
  assert.deepEqual(urls, ["/api/indra/sessions/s1/state?compact=true"]);
});
