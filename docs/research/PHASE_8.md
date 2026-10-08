# Phase 8: deploy Indra as one system

Phase 8 packages Postgres, migrations, the API, both workers and the dashboard so one command runs the whole product on any machine with Docker.

## Run it

```sh
cp deploy/.env.example deploy/.env      # set POSTGRES_PASSWORD and INDRA_API_KEY (openssl rand -base64 32)
docker compose --env-file deploy/.env up -d --build
```

Open `http://localhost:3000`, create the first account, and start researching. `docker compose --env-file deploy/.env logs -f research-worker` follows the worker; `down` stops everything and keeps the data volumes.

## What runs

| Service | Image | Role |
| --- | --- | --- |
| `postgres` | `pgvector/pgvector:0.8.1-pg17` | Durable state, with pgvector for passage embeddings |
| `migrate` | `docker/Dockerfile.backend` | Applies migrations once, then exits; everything else waits for it |
| `api` | backend | FastAPI on the internal network; published only on `127.0.0.1:8000` for CLI use |
| `research-worker` | backend | Research, Scout and synthesis jobs |
| `view-worker` | backend | Research maps and advisor results |
| `web` | `apps/web/Dockerfile` | Dashboard and its server-side proxy; the only service meant for browsers |

- **Accounts are on by default** in the compose file, with sign-up closed after the first account (`INDRA_ALLOW_SIGNUP=false`). Required secrets fail fast if missing.
- **The backend image** is built with uv from the locked dependencies, runs as a non-root user, includes Tesseract for OCR, and keeps the Hugging Face cache on a `models` volume so an embedding model downloads once. On Linux, PyTorch now resolves to its CPU-only build (`[tool.uv.sources]` in `pyproject.toml`), which removes several gigabytes of CUDA libraries from images and CI; macOS and Windows are unchanged.
- **The dashboard image** uses Next.js standalone output (enabled only when `NEXT_OUTPUT=standalone`, so local development and Vercel are unaffected) and runs as the `node` user.
- The API uses a five-second graceful shutdown so long-lived event streams close and browsers reconnect from their cursor.

## Exposing it beyond your computer

Put an HTTPS reverse proxy in front of the dashboard port, for example Caddy (`reverse_proxy localhost:3000`) or a cloud load balancer. The sign-in cookie is marked Secure automatically when requests arrive over HTTPS or with `X-Forwarded-Proto: https`. Do not publish the API port; browsers never need it.

Hosting choices (a VPS with Docker, a managed Postgres plus container hosting, or the dashboard on Vercel with the API elsewhere) are not decided here. The compose file is the reference layout for any of them.

## Verification — October 8, 2026

Docker is not installed on the development Mac, so the images and the stack are verified in CI: a new `compose` job builds both images, starts the stack with throwaway secrets, and runs `scripts/compose-smoke.sh` through the dashboard — signed-out requests refused, first sign-up succeeds and sets the cookie, a second sign-up is refused, a project and session are created and started, the research worker leases the job, and all five migrations are applied with pgvector.

Locally: the standalone dashboard build was run against an accounts-mode API (sign-in page served, signed-out proxy calls refused), the locked dependencies still install on macOS, and the backend suite passes.
