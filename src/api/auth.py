"""User accounts, sessions and per-resource authorization for the product API.

``INDRA_AUTH_MODE=accounts`` requires a signed-in user for every non-public
route and limits each user to their own projects and sessions. The default,
``off``, keeps the single-user local behaviour (with the optional shared
``INDRA_API_KEY``).

In accounts mode a request is authenticated by, in order:

- ``Authorization: Bearer <session token>`` — a user. Their identity always wins,
  so a trusted proxy that also sends the service key cannot widen their access.
- ``X-Indra-API-Key: <INDRA_API_KEY>`` without a user token — the service
  principal, used by workers and operators, with access to everything.

Resources owned by someone else answer 404, so their existence is not revealed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from .models import AuthCredentials, AuthResult, AuthStatus, User
from .repository import ConflictError, NotFoundError
from .security import _expected_api_key, _is_public_request, require_api_key

AUTH_MODE_ENV = "INDRA_AUTH_MODE"
ALLOW_SIGNUP_ENV = "INDRA_ALLOW_SIGNUP"
SESSION_DAYS = 30
# scrypt cost: ~50 ms and 16 MB per hash on a laptop.
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}
_PUBLIC_AUTH_PATHS = {"/auth/login", "/auth/register", "/auth/me"}
# Worker queue endpoints are for the service principal only.
_SERVICE_ONLY_PREFIXES = ("/jobs/lease", "/jobs/expire")


def auth_mode() -> str:
    return "accounts" if os.getenv(AUTH_MODE_ENV, "off").strip().lower() == "accounts" else "off"


def signup_allowed() -> bool:
    return os.getenv(ALLOW_SIGNUP_ENV, "true").strip().lower() not in {"0", "false", "no"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return "scrypt${n}${r}${p}${salt}${digest}".format(
        **_SCRYPT,
        salt=base64.b64encode(salt).decode(),
        digest=base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        # Spend the same work for unknown accounts so timing does not reveal them.
        hash_password(password)
        return False
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt),
            dklen=32,
            n=int(n),
            r=int(r),
            p=int(p),
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual, base64.b64decode(digest))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    kind: str  # "user", "service" or "local"
    user: User | None = None

    @property
    def owner_id(self) -> str | None:
        """Owner to scope reads and writes to; None means unrestricted."""

        return self.user.id if self.user else None


LOCAL = Principal("local")
SERVICE = Principal("service")


def principal(request: Request) -> Principal:
    return getattr(request.state, "principal", LOCAL)


def _unauthorized(detail: str, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail, "mode": "accounts", **extra},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authenticate(request: Request, call_next) -> Response:
    """Identify the caller; ownership is checked per route by ``authorize_path``."""

    if auth_mode() != "accounts":
        return await require_api_key(request, call_next)
    if _is_public_request(request):
        return await call_next(request)
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        user = request.app.state.repository.get_session_user(token_hash(token.strip()))
        if user is None:
            return _unauthorized("Your sign-in has expired. Sign in again.")
        request.state.principal = Principal("user", user)
        return await call_next(request)
    expected = _expected_api_key()
    provided = request.headers.get("x-indra-api-key", "").strip()
    if expected and provided and hmac.compare_digest(provided, expected):
        request.state.principal = SERVICE
        return await call_next(request)
    if request.url.path in _PUBLIC_AUTH_PATHS:
        return await call_next(request)
    return _unauthorized("Sign in to use Indra.")


_NOT_FOUND = {
    "project_id": "Project not found",
    "session_id": "Session not found",
    "branch_id": "Branch not found",
    "claim_id": "Claim not found",
    "job_id": "Job not found",
    "paper_id": "Paper not found",
}


def authorize_path(request: Request) -> None:
    """Route dependency: the caller must own every resource named in the path."""

    who = principal(request)
    if who.kind != "user":
        return
    if request.url.path.startswith(_SERVICE_ONLY_PREFIXES) or (
        request.url.path.startswith("/jobs/") and request.method != "GET"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Worker endpoints need the service key.")
    repository = request.app.state.repository
    for name, value in request.path_params.items():
        if name not in _NOT_FOUND:
            continue
        try:
            if name == "paper_id":
                allowed = repository.paper_visible_to(value, who.user.id)
            else:
                allowed = repository.resource_owner(name.removesuffix("_id"), value) == who.user.id
        except NotFoundError:
            allowed = False
        if not allowed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND[name])


router = APIRouter(prefix="/auth")


def _issue(repository, user: User) -> AuthResult:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    repository.create_user_session(user.id, token_hash(token), expires_at)
    return AuthResult(token=token, user=user, expires_at=expires_at)


@router.post("/register", response_model=AuthResult, status_code=status.HTTP_201_CREATED)
def register(payload: AuthCredentials, request: Request) -> AuthResult:
    if auth_mode() != "accounts":
        raise HTTPException(status.HTTP_409_CONFLICT, "Accounts are disabled (INDRA_AUTH_MODE=off).")
    repository = request.app.state.repository
    first = repository.count_users() == 0
    if not first and not signup_allowed():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "New accounts are disabled on this Indra server.")
    try:
        user = repository.create_user(payload.email, payload.name, hash_password(payload.password))
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.") from exc
    if first:
        # Work created before accounts were enabled belongs to the first account.
        repository.adopt_unowned(user.id)
    return _issue(repository, user)


@router.post("/login", response_model=AuthResult)
def login(payload: AuthCredentials, request: Request) -> AuthResult:
    if auth_mode() != "accounts":
        raise HTTPException(status.HTTP_409_CONFLICT, "Accounts are disabled (INDRA_AUTH_MODE=off).")
    repository = request.app.state.repository
    found = repository.get_user_credentials(payload.email)
    user, stored = found if found else (None, None)
    if not verify_password(payload.password, stored) or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    return _issue(repository, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if auth_mode() == "accounts" and scheme.lower() == "bearer" and token.strip():
        request.app.state.repository.delete_user_session(token_hash(token.strip()))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthStatus)
def me(request: Request) -> AuthStatus | JSONResponse:
    if auth_mode() != "accounts":
        return AuthStatus(mode="off")
    who = principal(request)
    repository = request.app.state.repository
    open_signup = signup_allowed() or repository.count_users() == 0
    if who.kind == "local":
        # Signed out: the sign-in page still needs to know whether it may offer sign-up.
        return _unauthorized("Sign in to use Indra.", signup_open=open_signup)
    return AuthStatus(
        mode="accounts",
        user=who.user,
        signup_open=open_signup,
    )
