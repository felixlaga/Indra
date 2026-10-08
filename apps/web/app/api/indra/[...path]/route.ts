import type { NextRequest } from "next/server";

import { SESSION_COOKIE, upstreamHeaders, upstreamUrl } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// Only these request headers reach the API; Authorization comes from the cookie alone.
const FORWARDED_REQUEST_HEADERS = ["accept", "content-type", "last-event-id"];
const FORWARDED_RESPONSE_HEADERS = [
  "content-type",
  "content-disposition",
  "cache-control",
  "retry-after",
  "x-indra-validation-preserved",
];

async function forward(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  const search = new URL(request.url).search;
  const headers = upstreamHeaders(request.cookies.get(SESSION_COOKIE)?.value);
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await fetch(
      upstreamUrl(`/${path.map(encodeURIComponent).join("/")}${search}`),
      {
        method: request.method,
        headers,
        body: hasBody ? await request.arrayBuffer() : undefined,
        cache: "no-store",
        redirect: "manual",
        signal: request.signal,
      },
    );
  } catch {
    return Response.json(
      { detail: "The Indra API is not reachable. Check that it is running." },
      { status: 502 },
    );
  }
  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  // Streams (server-sent events) pass through without buffering.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
