"""Account, sign-in session and ownership storage for both repository backends."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from .models import User


def _is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except ValueError:
        return False
    return True


class MemoryAccounts:
    """Accounts for the in-process repository; owners live beside projects and sessions."""

    def count_users(self) -> int:
        with self._lock:
            return len(self._users)

    def create_user(self, email: str, name: str | None, password_hash: str) -> User:
        from .repository import ConflictError, utc_now

        with self._lock:
            if any(u.email == email for u in self._users.values()):
                raise ConflictError("Email already registered")
            user = User(id=self._new_id("user"), email=email, name=name, created_at=utc_now())
            self._users[user.id] = user
            self._password_hashes[user.id] = password_hash
            return user

    def get_user_credentials(self, email: str) -> tuple[User, str] | None:
        with self._lock:
            for user in self._users.values():
                if user.email == email:
                    return user, self._password_hashes[user.id]
            return None

    def create_user_session(self, user_id: str, token_hash: str, expires_at: datetime) -> None:
        with self._lock:
            self._user_sessions[token_hash] = (user_id, expires_at)

    def get_session_user(self, token_hash: str) -> User | None:
        with self._lock:
            found = self._user_sessions.get(token_hash)
            if not found or found[1] <= datetime.now(timezone.utc):
                return None
            return self._users.get(found[0])

    def delete_user_session(self, token_hash: str) -> None:
        with self._lock:
            self._user_sessions.pop(token_hash, None)

    def adopt_unowned(self, user_id: str) -> None:
        with self._lock:
            for project_id in self._projects:
                self._project_owner.setdefault(project_id, user_id)
            for session_id in self._sessions:
                self._session_owner.setdefault(session_id, user_id)

    def resource_owner(self, kind: str, resource_id: str) -> str | None:
        """Owner of a project, session, branch, claim or job (NotFoundError if absent)."""

        with self._lock:
            if kind == "project":
                self.get_project(resource_id)
                return self._project_owner.get(resource_id)
            session_id = {
                "session": lambda: self._get_session_unlocked(resource_id).id,
                "branch": lambda: self._get_branch_unlocked(resource_id).session_id,
                "claim": lambda: self._get_claim_unlocked(resource_id).session_id,
                "job": lambda: self._get_job_unlocked(resource_id).session_id,
            }[kind]()
            return self._session_owner.get(session_id)

    def paper_visible_to(self, paper_id: str, owner_id: str) -> bool:
        with self._lock:
            paper = self._get_paper_unlocked(paper_id)
            return any(
                link.paper_id == paper.id and self._session_owner.get(link.session_id) == owner_id
                for link in self._session_papers.values()
            )


class PostgresAccounts:
    def count_users(self) -> int:
        with self._connect() as conn:
            return self._fetch_one(conn, "SELECT count(*) AS n FROM users")["n"]

    def create_user(self, email: str, name: str | None, password_hash: str) -> User:
        from .repository import ConflictError

        with self._connect() as conn:
            row = self._fetch_optional(
                conn,
                """INSERT INTO users(email, name, password_hash) VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING RETURNING *""",
                (email, name, password_hash),
            )
        if row is None:
            raise ConflictError("Email already registered")
        return _user(row)

    def get_user_credentials(self, email: str) -> tuple[User, str] | None:
        with self._connect() as conn:
            row = self._fetch_optional(conn, "SELECT * FROM users WHERE email=%s", (email,))
        return (_user(row), row["password_hash"]) if row else None

    def create_user_session(self, user_id: str, token_hash: str, expires_at: datetime) -> None:
        with self._connect() as conn:
            self._execute(
                conn,
                "INSERT INTO user_sessions(token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                (token_hash, user_id, expires_at),
            )

    def get_session_user(self, token_hash: str) -> User | None:
        with self._connect() as conn:
            row = self._fetch_optional(
                conn,
                """UPDATE user_sessions SET last_used_at=now()
                WHERE token_hash=%s AND expires_at > now()
                RETURNING user_id""",
                (token_hash,),
            )
            if row is None:
                return None
            user = self._fetch_optional(conn, "SELECT * FROM users WHERE id=%s", (row["user_id"],))
        return _user(user) if user else None

    def delete_user_session(self, token_hash: str) -> None:
        with self._connect() as conn:
            self._execute(conn, "DELETE FROM user_sessions WHERE token_hash=%s", (token_hash,))

    def adopt_unowned(self, user_id: str) -> None:
        with self._connect() as conn:
            self._execute(conn, "UPDATE projects SET user_id=%s WHERE user_id IS NULL", (user_id,))
            self._execute(
                conn, "UPDATE research_sessions SET user_id=%s WHERE user_id IS NULL", (user_id,)
            )

    def resource_owner(self, kind: str, resource_id: str) -> str | None:
        """Owner of a project, session, branch, claim or job (NotFoundError if absent)."""

        from .repository import NotFoundError

        queries = {
            "project": "SELECT user_id FROM projects WHERE id=%s",
            "session": "SELECT user_id FROM research_sessions WHERE id=%s",
            "branch": """SELECT s.user_id FROM branches b
                JOIN research_sessions s ON s.id=b.session_id WHERE b.id=%s""",
            "claim": """SELECT s.user_id FROM claims c
                JOIN research_sessions s ON s.id=c.session_id WHERE c.id=%s""",
            "job": """SELECT s.user_id FROM jobs j
                JOIN research_sessions s ON s.id=j.session_id WHERE j.id=%s""",
        }
        if not _is_uuid(resource_id):
            raise NotFoundError(f"{kind.title()} not found")
        with self._connect() as conn:
            row = self._fetch_optional(conn, queries[kind], (resource_id,))
        if row is None:
            raise NotFoundError(f"{kind.title()} not found")
        return str(row["user_id"]) if row["user_id"] else None

    def paper_visible_to(self, paper_id: str, owner_id: str) -> bool:
        with self._connect() as conn:
            paper = self._get_paper_row(conn, paper_id)
            row = self._fetch_optional(
                conn,
                """SELECT 1 FROM session_papers sp JOIN research_sessions s ON s.id=sp.session_id
                WHERE sp.paper_id=%s AND s.user_id=%s LIMIT 1""",
                (paper["id"], owner_id),
            )
        return row is not None


def _user(row: dict) -> User:
    return User(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        created_at=row["created_at"],
    )
