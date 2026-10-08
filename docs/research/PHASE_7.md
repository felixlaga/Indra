# Phase 7: accounts and server-side credentials

Before this phase Indra had one optional shared key, `INDRA_API_KEY`, which the dashboard put in the browser bundle (`NEXT_PUBLIC_INDRA_API_KEY`) where anyone using the page could read it. Phase 7 adds user accounts with per-user data and moves every credential behind the dashboard's server.

## Modes

| `INDRA_AUTH_MODE` | Behaviour |
| --- | --- |
| `off` (default) | Single-user local mode, as before. If `INDRA_API_KEY` is set, requests need it. |
| `accounts` | Every non-public route needs a signed-in user, and each user sees only their own projects and sessions. |

Turning accounts on for an existing database is safe: the first account created adopts every project and session that has no owner. Set `INDRA_ALLOW_SIGNUP=false` to stop further sign-ups (the first account is always allowed).

## How requests are authenticated

- **Users** sign in with email and password (`POST /auth/register`, `/auth/login`, `/auth/logout`, `GET /auth/me`). Passwords are hashed with scrypt from the Python standard library. Sign-in tokens are random 256-bit values; only their SHA-256 is stored (`user_sessions`), they last 30 days and logout revokes them. Unknown emails cost the same hashing time as wrong passwords.
- **Service** callers (workers, operators) send `X-Indra-API-Key: <INDRA_API_KEY>` and can reach everything, including the job-queue endpoints, which users cannot.
- A user token always wins over the service key, so a caller that sends both is limited to that user's data.

## Ownership on every route

A route dependency checks every resource named in the path — project, session, branch, claim, job or paper — against the signed-in user. Anything owned by someone else answers **404**, so its existence is not revealed. Project and session lists are filtered to the owner, and a session can only be created in one's own project. Papers are shared across sessions; a user can open a paper only if one of their sessions contains it.

`test_accounts.py` walks every route in the app with another user's IDs and fails if any returns data, so a future route without an ownership check fails the suite.

## Dashboard

- The browser talks only to the dashboard (`/api/indra/*`, `/api/auth/*`). Its server forwards requests to `INDRA_API_URL`, adding the user's token from an **HTTP-only, SameSite=Lax cookie** (Secure over HTTPS, including behind a proxy that sets `X-Forwarded-Proto`). Only an allow-list of headers is forwarded, so a page cannot inject its own `Authorization`.
- `INDRA_API_KEY` in `apps/web/.env.local` stays on the server. It is forwarded as `X-Indra-Proxy-Key`, which unlocks a shared-key deployment when accounts are off and grants nothing when they are on; a signed-out visitor never gains service access through the dashboard.
- Server-sent events and export downloads go through the same proxy, so no key appears in URLs any more.
- With accounts on, an expired or missing sign-in redirects to `/login` and back to the page afterwards. The header shows the account and **Sign out**.

`NEXT_PUBLIC_INDRA_API_KEY` is no longer read. `NEXT_PUBLIC_INDRA_API_URL` still works as a fallback for `INDRA_API_URL`.

## Upgrade

Apply migration `0005_accounts.sql` (password hashes, `user_sessions`, `research_sessions.user_id`, owner indexes). Move any dashboard key from `NEXT_PUBLIC_INDRA_API_KEY` to `INDRA_API_KEY` in `apps/web/.env.local`.

## Verification — October 8, 2026

- 213 backend tests against memory and real Postgres, including the all-routes ownership walk (checked to fail when one router lacks the dependency), service-key precedence, proxy-key behaviour in both modes, worker endpoints, adoption by the first account, login, logout, expiry, duplicate emails and closed sign-up.
- 26 frontend tests (same-origin client, sign-in redirect keeping the current page, server-side proxy headers), TypeScript checking and the production build.
- Browser check with accounts on: redirect to sign-in, account creation adopting existing projects, `document.cookie` without the token, the API refusing direct unauthenticated calls, live session updates through the proxy, sign-out, and the redirect back after signing in.

Not included: password reset and email verification (there is no mail delivery), rate limiting of sign-in attempts, and sharing a project with other users.
