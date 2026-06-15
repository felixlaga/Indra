# ERLA Database Migrations

This directory contains SQL migrations for the durable ERLA product database.

The initial migration is:

- `0001_initial_product_schema.sql`

It creates the Postgres tables described in `DATA_MODEL.md` for projects, research sessions, branches, papers, chunks, summaries, claims, evidence, validations, hypotheses, agent decisions, events, and exports.

Apply manually during local experimentation:

```bash
psql "$DATABASE_URL" -f migrations/0001_initial_product_schema.sql
```

Requirements:

- PostgreSQL.
- `pgcrypto` for `gen_random_uuid()`.
- `pgvector` for the nullable `paper_chunks.embedding` column.

This migration only creates schema. It does not replace the in-memory API repository, add a migration runner, start workers, or connect runtime code to Postgres.
