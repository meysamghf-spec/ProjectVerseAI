"""Sign-in, sign-out, password change, and administrator user management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes import api_error, get_current_user, require_admin, session_token
from app.auth import (
    CSRF_HEADER,
    ROLES,
    SESSION_COOKIE,
    LoginLimiter,
    active_admin_count,
    authenticate,
    create_session,
    create_user,
    hash_password,
    normalize_email,
    public_user,
    revoke_all,
    revoke_token,
    user_for_token,
    validate_password,
)
from app.config import Settings, get_settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/v1")
_limiters: dict[int, LoginLimiter] = {}


def _limiter(settings: Settings) -> LoginLimiter:
    limiter = _limiters.get(settings.login_max_failures)
    if limiter is None:
        limiter = _limiters[settings.login_max_failures] = LoginLimiter(settings.login_max_failures)
    return limiter


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UserCreateBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    role: str = "user"
    display_name: str = Field(default="", max_length=120)


class UserUpdateBody(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    display_name: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=256)


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.post("/auth/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    if settings.auth_mode != "accounts":
        api_error(400, "accounts_disabled", "User accounts are not enabled on this server (AUTH_MODE).")
    if not request.headers.get(CSRF_HEADER):
        # Blocks cross-site form posts that would sign the browser into another account.
        api_error(403, "csrf", "Missing X-Requested-With header.")
    email = normalize_email(body.email)
    client = request.client.host if request.client else ""
    keys = (f"email:{email}", f"ip:{client}")
    limiter = _limiter(settings)
    if limiter.blocked(*keys):
        api_error(429, "too_many_attempts", "Too many failed sign-in attempts. Wait 15 minutes and try again.")
    user = authenticate(db, email, body.password)
    if user is None:
        limiter.fail(*keys)
        api_error(401, "invalid_credentials", "The email or password is not correct.")
    limiter.reset(f"email:{email}")
    token = create_session(db, user, settings)
    _set_cookie(response, token, settings)
    return {"user": public_user(user)}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    token, _ = session_token(request)
    revoke_token(db, token)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/auth/me")
def me(request: Request, settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> dict:
    user = None
    if settings.auth_mode == "accounts":
        token, _ = session_token(request)
        user = user_for_token(db, token)
    return {
        "auth_mode": settings.auth_mode,
        "authenticated": user is not None or settings.auth_mode != "accounts",
        "user": public_user(user) if user else None,
    }


@router.post("/auth/password", status_code=204)
def change_password(
    body: PasswordBody,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if authenticate(db, user.email, body.current_password) is None:
        api_error(400, "invalid_credentials", "The current password is not correct.")
    problem = validate_password(body.new_password)
    if problem:
        api_error(422, "weak_password", problem)
    user.password_hash = hash_password(body.new_password)
    db.commit()
    token, _ = session_token(request)
    revoke_all(db, user, keep_token=token)
    return Response(status_code=204)


@router.get("/admin/users")
def list_users(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    users = db.query(User).order_by(User.created_at).all()
    return {"items": [public_user(user) for user in users], "roles": list(ROLES)}


@router.post("/admin/users", status_code=201)
def admin_create_user(
    body: UserCreateBody, _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    try:
        user = create_user(db, body.email, body.password, role=body.role, display_name=body.display_name)
    except LookupError as exc:
        api_error(409, "conflict", str(exc))
    except ValueError as exc:
        api_error(422, "invalid_user", str(exc))
    return {"user": public_user(user)}


@router.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: str,
    body: UserUpdateBody,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        api_error(404, "not_found", "User not found.")
    demoting = body.role is not None and body.role != "admin" and user.role == "admin"
    disabling = body.is_active is False and user.is_active and user.role == "admin"
    if (demoting or disabling) and active_admin_count(db) <= 1:
        api_error(409, "last_admin", "At least one active administrator must remain.")
    if body.role is not None:
        if body.role not in ROLES:
            api_error(422, "invalid_role", f"Role must be one of: {', '.join(ROLES)}.")
        user.role = body.role
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    revoke = False
    if body.password is not None:
        problem = validate_password(body.password)
        if problem:
            api_error(422, "weak_password", problem)
        user.password_hash = hash_password(body.password)
        revoke = True
    if body.is_active is not None:
        user.is_active = body.is_active
        revoke = revoke or not body.is_active
    db.commit()
    if revoke and user.id != admin.id:
        revoke_all(db, user)
    db.refresh(user)
    return {"user": public_user(user)}
