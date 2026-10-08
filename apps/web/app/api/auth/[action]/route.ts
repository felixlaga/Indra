import { NextResponse, type NextRequest } from "next/server";

import {
  SESSION_COOKIE,
  sessionCookie,
  upstreamHeaders,
  upstreamUrl,
} from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

/** Sign in, create an account, or sign out; the token stays in an HTTP-only cookie. */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ action: string }> },
): Promise<Response> {
  const { action } = await params;
  if (!["login", "register", "logout"].includes(action)) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const headers = upstreamHeaders(action === "logout" ? token : undefined);
  headers.set("Content-Type", "application/json");
  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl(`/auth/${action}`), {
      method: "POST",
      headers,
      body: action === "logout" ? undefined : await request.text(),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: "The Indra API is not reachable. Check that it is running." },
      { status: 502 },
    );
  }
  if (action === "logout") {
    const response = new NextResponse(null, { status: 204 });
    response.cookies.delete(SESSION_COOKIE);
    return response;
  }
  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return Response.json(body, { status: upstream.status });
  }
  const response = NextResponse.json({ user: body.user }, { status: upstream.status });
  // Behind a TLS-terminating proxy the app itself sees plain HTTP.
  const secure =
    new URL(request.url).protocol === "https:" ||
    request.headers.get("x-forwarded-proto") === "https";
  response.cookies.set(sessionCookie(body.token, new Date(body.expires_at), secure));
  return response;
}
