"""Bounded, cursor-based event reads for both repository backends."""

from uuid import UUID
from .models import Event


class MemoryEventReads:
    def event_position(self, session_id: str, cursor: str | None = None) -> int:
        from .repository import ConflictError

        with self._lock:
            self._get_session_unlocked(session_id)
            events = self._list_events_unlocked(session_id)
            if cursor is None:
                return events[-1].sequence if events else 0
            if str(cursor).isdigit():
                position = int(cursor)
                if 0 <= position <= (events[-1].sequence if events else 0):
                    return position
            for event in events:
                if event.id == cursor:
                    return event.sequence
            raise ConflictError(
                "Event cursor does not belong to this session; reload the session."
            )

    def read_events(
        self,
        session_id: str,
        *,
        after: int = 0,
        before: int | None = None,
        limit: int = 100,
    ) -> list[Event]:
        with self._lock:
            self._get_session_unlocked(session_id)
            events = [
                e
                for e in self._list_events_unlocked(session_id)
                if e.sequence > after and (before is None or e.sequence < before)
            ]
            return events[:limit] if before is None else events[-limit:]

    def view_revision(self, session_id: str) -> int:
        with self._lock:
            self._get_session_unlocked(session_id)
            return max(
                (
                    e.sequence
                    for e in self._list_events_unlocked(session_id)
                    if e.event_type != "research_progress"
                    and not e.event_type.startswith("derived_view_")
                ),
                default=0,
            )


class PostgresEventReads:
    def event_position(self, session_id: str, cursor: str | None = None) -> int:
        from .repository import ConflictError

        with self._connect() as conn:
            self._get_session(conn, session_id)
            row = self._fetch_one(
                conn,
                "SELECT COALESCE(max(sequence),0) AS position FROM session_event_counters WHERE session_id=%s",
                (session_id,),
            )
            latest = row["position"]
            if cursor is None:
                return latest
            if str(cursor).isdigit() and 0 <= int(cursor) <= latest:
                return int(cursor)
            try:
                UUID(str(cursor))
            except ValueError:
                raise ConflictError(
                    "Invalid event cursor; reload the session."
                ) from None
            rows = self._fetch_all(
                conn,
                "SELECT sequence FROM events WHERE session_id=%s AND id=%s",
                (session_id, cursor),
            )
            if rows:
                return rows[0]["sequence"]
            raise ConflictError(
                "Event cursor does not belong to this session; reload the session."
            )

    def read_events(
        self,
        session_id: str,
        *,
        after: int = 0,
        before: int | None = None,
        limit: int = 100,
    ) -> list[Event]:
        from .postgres_repository import _event_from_row

        with self._connect() as conn:
            self._get_session(conn, session_id)
            if before is None:
                rows = self._fetch_all(
                    conn,
                    "SELECT * FROM events WHERE session_id=%s AND sequence>%s ORDER BY sequence LIMIT %s",
                    (session_id, after, limit),
                )
            else:
                rows = self._fetch_all(
                    conn,
                    "SELECT * FROM events WHERE session_id=%s AND sequence>%s AND sequence<%s ORDER BY sequence DESC LIMIT %s",
                    (session_id, after, before, limit),
                )
                rows.reverse()
            return [_event_from_row(row) for row in rows]

    def view_revision(self, session_id: str) -> int:
        with self._connect() as conn:
            self._get_session(conn, session_id)
            row = self._fetch_one(
                conn,
                "SELECT COALESCE(max(revision),0) AS revision FROM session_event_counters WHERE session_id=%s",
                (session_id,),
            )
            return row["revision"]
