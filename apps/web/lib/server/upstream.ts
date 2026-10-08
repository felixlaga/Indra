/**
 * Server-only helpers for reaching the Indra API. The browser never sees the
 * API address, the service key or the sign-in token: it talks to this app,
 * which forwards requests with the token from an HTTP-only cookie.
 */

export const SESSION_COOKIE = "indra_session";

export function upstreamUrl(path: string): string {
  const base = (
    process.env.INDRA_API_URL ??
    process.env.NEXT_PUBLIC_INDRA_API_URL ??
    "http://localhost:8000"
  ).replace(/\/$/, "");
  return `${base}${path}`;
}

/**
 * Headers for an upstream call. The service key travels as a proxy key: it
 * unlocks a shared-key deployment but never grants access on its own when
 * accounts are enabled.
 */
export function upstreamHeaders(token?: string): Headers {
  const headers = new Headers();
  const key = process.env.INDRA_API_KEY?.trim();
  if (key) headers.set("X-Indra-Proxy-Key", key);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export function sessionCookie(token: string, expires: Date, secure: boolean) {
  return {
    name: SESSION_COOKIE,
    value: token,
    httpOnly: true,
    sameSite: "lax" as const,
    secure,
    path: "/",
    expires,
  };
}
