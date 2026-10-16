"""User accounts: scrypt password hashing, server-side sessions, roles, and bootstrap.

Sessions are opaque random tokens sent in an HttpOnly cookie (or an Authorization: Bearer
header for scripts). The database stores only a SHA-256 of each token, so a database leak
does not reveal usable sessions.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AuthSession, Project, User

logger = logging.getLogger("projectverse.auth")

ROLES = ("admin", "user")
SESSION_COOKIE = "pv_session"
CSRF_HEADER = "x-requested-with"
MIN_PASSWORD_LENGTH = 10
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def validate_email(value: str) -> str | None:
    if not _EMAIL.fullmatch(normalize_email(value)):
        return "Enter a valid email address."
    return None


def validate_password(value: str) -> str | None:
    if len(value or "") < MIN_PASSWORD_LENGTH:
        return f"Passwords must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(value) > 256:
        return "Passwords must be at most 256 characters."
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    encode = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${encode(salt)}${encode(digest)}"


def verify_password(stored: str, password: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# A fixed dummy hash keeps login timing similar for unknown and known emails.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == normalize_email(email)).one_or_none()
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(user.password_hash, password) or not user.is_active:
        return None
    return user


def create_session(db: Session, user: User, settings: Settings) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(token),
            expires_at=now + timedelta(hours=settings.session_hours),
        )
    )
    user.last_login_at = now
    # Opportunistic cleanup of this user's expired sessions.
    for old in list(user.sessions):
        if old.expires_at is not None and _aware(old.expires_at) < now:
            db.delete(old)
    db.commit()
    return token


def user_for_token(db: Session, token: str) -> User | None:
    if not token:
        return None
    row = db.query(AuthSession).filter(AuthSession.token_hash == _token_hash(token)).one_or_none()
    if row is None:
        return None
    if _aware(row.expires_at) < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_token(db: Session, token: str) -> None:
    if not token:
        return
    db.query(AuthSession).filter(AuthSession.token_hash == _token_hash(token)).delete()
    db.commit()


def revoke_all(db: Session, user: User, keep_token: str | None = None) -> None:
    query = db.query(AuthSession).filter(AuthSession.user_id == user.id)
    if keep_token:
        query = query.filter(AuthSession.token_hash != _token_hash(keep_token))
    query.delete(synchronize_session=False)
    db.commit()


def create_user(db: Session, email: str, password: str, role: str = "user", display_name: str = "") -> User:
    problem = validate_email(email) or validate_password(password)
    if problem:
        raise ValueError(problem)
    if role not in ROLES:
        raise ValueError(f"Role must be one of: {', '.join(ROLES)}.")
    normalized = normalize_email(email)
    if db.query(User).filter(User.email == normalized).first() is not None:
        raise LookupError("An account with that email already exists.")
    user = User(
        email=normalized,
        display_name=(display_name or "").strip()[:120],
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def active_admin_count(db: Session) -> int:
    return db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()


def bootstrap_admin(db: Session, settings: Settings) -> User | None:
    """Create the first administrator from INITIAL_ADMIN_* when the users table is empty."""

    if settings.auth_mode != "accounts" or db.query(User).count() > 0:
        return None
    email, password = settings.initial_admin_email, settings.initial_admin_password
    if not email or not password:
        logger.warning("Accounts mode has no users. Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD once.")
        return None
    user = create_user(db, email, password, role="admin", display_name="Administrator")
    logger.info("Created the initial administrator account. Remove INITIAL_ADMIN_PASSWORD from the environment.")
    legacy = (settings.legacy_owner_id or "").strip()
    if legacy:
        moved = db.query(Project).filter(Project.owner_id == legacy).update({Project.owner_id: user.id})
        db.commit()
        logger.info("Assigned %s existing project(s) from the legacy owner to the administrator.", moved)
    return user


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


class LoginLimiter:
    """Failed-login limiter per email and per client address, in process memory."""

    def __init__(self, max_failures: int, window_seconds: int = 900) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        items = [stamp for stamp in self._failures.get(key, []) if now - stamp < self.window]
        self._failures[key] = items
        return items

    def blocked(self, *keys: str) -> bool:
        now = time.monotonic()
        with self._lock:
            return any(len(self._recent(key, now)) >= self.max_failures for key in keys if key)

    def fail(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                if key:
                    self._recent(key, now).append(now)

    def reset(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._failures.pop(key, None)
