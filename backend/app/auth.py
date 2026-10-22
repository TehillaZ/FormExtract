"""Two roles, each with a password from .env (USER_PASSWORD, DEVELOPER_PASSWORD).

Logging in with a password sets a signed, HTTP-only cookie holding the role; every API route except /health and
/auth/* needs it, and the accuracy and repeated-mistakes routes need the developer role. The cookie is signed with
the role's own password, so changing a password signs everybody in with it out. A role whose password is not set
cannot log in at all (there is no default password)."""
from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Literal

from fastapi import Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

from app.config import settings

Role = Literal["user", "developer"]
COOKIE = "session"


def _password(role: Role) -> str:
    return settings.user_password if role == "user" else settings.developer_password


def _sign(role: Role) -> str:
    return hmac.new(_password(role).encode(), role.encode(), hashlib.sha256).hexdigest()


def role_for_password(password: str) -> Role | None:
    for role in ("developer", "user"):
        expected = _password(role)   # type: ignore[arg-type]
        if expected and hmac.compare_digest(password.encode(), expected.encode()):
            return role   # type: ignore[return-value]
    return None


def start_session(response: Response, role: Role) -> None:
    response.set_cookie(COOKIE, f"{role}.{_sign(role)}", httponly=True, samesite="lax", max_age=60 * 60 * 12)


def end_session(response: Response) -> None:
    response.delete_cookie(COOKIE)


def current_role(session: Annotated[str | None, Cookie()] = None) -> Role:
    role, _, signature = (session or "").partition(".")
    if role in ("user", "developer") and _password(role) and hmac.compare_digest(signature, _sign(role)):   # type: ignore[arg-type]
        return role   # type: ignore[return-value]
    raise HTTPException(401, "יש להתחבר")


def require_developer(role: Annotated[Role, Depends(current_role)]) -> Role:
    if role != "developer":
        raise HTTPException(403, "המסך הזה מיועד למפתחים בלבד")
    return role


class Login(BaseModel):
    password: str


class Me(BaseModel):
    role: Role
