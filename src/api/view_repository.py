"""Durable coalesced work queue for map/advisor read models.

Separate from research jobs: read models can be built for paused, cancelled and
completed sessions and must never change the research lifecycle.
"""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
from typing import Any

LEASE_SECONDS = 120
MAX_ATTEMPTS = 3
# Bump when map or advisor output changes, so results cached by older code are rebuilt
# on their next request instead of being served. 2: model hypotheses in advice.
# 3: discovered (found but unread) papers on the map. 4: field insight and themes.
BUILDER_VERSION = 4


def outdated(row: dict) -> bool:
    return row["status"] == "ready" and (row.get("result") or {}).get(
        "builder_version"
    ) != BUILDER_VERSION


class MemoryViewWrites:
    def request_views(self, session_id: str, *, retry: bool = False) -> dict[str, Any]:
        from .repository import utc_now

        with self._lock:
            revision = self.view_revision(session_id)
            row = self._research_views.get(session_id)
            if row is None:
                row = dict(
                    session_id=session_id,
                    requested_revision=revision,
                    source_revision=None,
                    status="queued",
                    lease_token=None,
                    lease_until=None,
                    attempts=0,
                    result={},
                    error=None,
                    updated_at=utc_now(),
                )
                self._research_views[session_id] = row
            elif (
                row["requested_revision"] != revision
                or (retry and row["status"] == "failed")
                or outdated(row)
            ):
                row.update(requested_revision=revision, attempts=0, error=None)
                if row["status"] != "running":
                    row["status"] = "queued"
            return deepcopy(row)

    def lease_views(self) -> dict[str, Any] | None:
        from .repository import utc_now

        with self._lock:
            for row in self._research_views.values():
                expired = row["status"] == "running" and row["lease_until"] < utc_now()
                if expired and row["attempts"] >= MAX_ATTEMPTS:
                    row.update(
                        status="failed",
                        error="View worker repeatedly timed out. Retry to rebuild.",
                    )
                elif row["status"] == "queued" or expired:
                    row.update(
                        status="running",
                        lease_token=str(uuid4()),
                        lease_until=utc_now() + timedelta(seconds=LEASE_SECONDS),
                        attempts=row["attempts"] + 1,
                    )
                    return deepcopy(row)
            return None

    def finish_views(
        self,
        leased: dict[str, Any],
        result: dict | None = None,
        error: str | None = None,
    ) -> bool:
        from .repository import utc_now

        with self._lock:
            row = self._research_views[leased["session_id"]]
            if (
                row["lease_token"] != leased["lease_token"]
                or row["lease_until"] < utc_now()
            ):
                return False
            revision = self.view_revision(leased["session_id"])
            stale = revision != leased["requested_revision"]
            status = "queued" if stale else ("failed" if error else "ready")
            row.update(
                status=status,
                requested_revision=revision,
                lease_token=None,
                lease_until=None,
                error=error,
                updated_at=utc_now(),
            )
            if stale:
                row.update(attempts=0, error=None)
            elif not error:
                row.update(source_revision=revision, result=result)
            self._create_event_unlocked(
                leased["session_id"],
                "derived_view_failed" if error else "derived_view_completed",
                {"status": status, "source_revision": leased["requested_revision"]},
            )
            return True


class PostgresViewWrites:
    def request_views(self, session_id: str, *, retry: bool = False) -> dict[str, Any]:
        # INSERT .. ON CONFLICT coalesces concurrent requests into one work item.
        revision = self.view_revision(session_id)
        with self._connect() as conn:
            return self._fetch_one(
                conn,
                """
                INSERT INTO session_research_views(session_id,requested_revision,status)
                VALUES (%(session_id)s,%(revision)s,'queued') ON CONFLICT(session_id) DO UPDATE SET
                  requested_revision=GREATEST(session_research_views.requested_revision,EXCLUDED.requested_revision),
                  status=CASE WHEN session_research_views.status='running' THEN 'running'
                    WHEN session_research_views.requested_revision<EXCLUDED.requested_revision
                      OR (%(retry)s AND session_research_views.status='failed')
                      OR (session_research_views.status='ready'
                          AND session_research_views.result->>'builder_version' IS DISTINCT FROM %(version)s)
                      THEN 'queued'
                    ELSE session_research_views.status END,
                  attempts=CASE WHEN session_research_views.requested_revision<EXCLUDED.requested_revision
                      OR (%(retry)s AND session_research_views.status='failed') THEN 0 ELSE session_research_views.attempts END,
                  error=CASE WHEN session_research_views.requested_revision<EXCLUDED.requested_revision
                      OR (%(retry)s AND session_research_views.status='failed') THEN NULL ELSE session_research_views.error END
                RETURNING *
            """,
                {
                    "session_id": session_id,
                    "revision": revision,
                    "retry": retry,
                    "version": str(BUILDER_VERSION),
                },
            )

    def lease_views(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            self._execute(
                conn,
                """UPDATE session_research_views SET status='failed',
                error='View worker repeatedly timed out. Retry to rebuild.'
                WHERE status='running' AND lease_until<now() AND attempts >= %s""",
                (MAX_ATTEMPTS,),
            )
            rows = self._fetch_all(
                conn,
                """
                WITH candidate AS (
                  SELECT session_id FROM session_research_views
                  WHERE status='queued' OR (status='running' AND lease_until<now())
                  ORDER BY updated_at FOR UPDATE SKIP LOCKED LIMIT 1
                ) UPDATE session_research_views v SET status='running', lease_token=%s,
                  lease_until=now() + %s * interval '1 second', attempts=attempts+1
                FROM candidate c WHERE v.session_id=c.session_id RETURNING v.*
            """,
                (uuid4(), LEASE_SECONDS),
            )
            return rows[0] if rows else None

    def finish_views(
        self,
        leased: dict[str, Any],
        result: dict | None = None,
        error: str | None = None,
    ) -> bool:
        from .postgres_repository import _jsonb

        revision = self.view_revision(str(leased["session_id"]))
        stale = revision != leased["requested_revision"]
        status = "queued" if stale else ("failed" if error else "ready")
        with self._connect() as conn:
            rows = self._fetch_all(
                conn,
                """
                UPDATE session_research_views SET status=CASE WHEN requested_revision>%s THEN 'queued' ELSE %s END, lease_token=NULL, lease_until=NULL,
                    source_revision=CASE WHEN %s THEN %s ELSE source_revision END,
                    result=CASE WHEN %s THEN %s ELSE result END,
                    requested_revision=GREATEST(requested_revision,%s),
                    error=%s, attempts=CASE WHEN %s THEN 0 ELSE attempts END, updated_at=now()
                WHERE session_id=%s AND lease_token=%s AND lease_until>now() RETURNING session_id
            """,
                (
                    leased["requested_revision"],
                    status,
                    not stale and not error,
                    leased["requested_revision"],
                    not stale and not error,
                    _jsonb(result or {}),
                    revision,
                    None if stale else error,
                    stale,
                    leased["session_id"],
                    leased["lease_token"],
                ),
            )
            if not rows:
                return False
            self._insert_event(
                conn,
                session_id=str(leased["session_id"]),
                event_type="derived_view_failed" if error else "derived_view_completed",
                payload={
                    "status": status,
                    "source_revision": leased["requested_revision"],
                },
            )
            return True
