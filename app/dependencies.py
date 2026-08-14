"""Reusable auth guard.

Every protected route depends on `require_auth`, so the header parsing and the
Supabase token check live in exactly one place. A route body only ever runs
after the token has been verified.
"""

from typing import Any, NamedTuple, Optional

from fastapi import Depends, Header, HTTPException, status
from supabase_auth.errors import AuthError, AuthRetryableError

from app.supabase_client import supabase


class AuthContext(NamedTuple):
    """The verified user plus the raw token, which logout still needs."""

    token: str
    user: Any


def extract_bearer_token(authorization: Optional[str]) -> str:
    """Pull the token out of `Authorization: Bearer <token>`.

    Raises 401 when the header is absent, is not the Bearer scheme, or carries
    an empty token. The scheme match is case-insensitive because RFC 7235 says
    scheme names are, and real clients send "bearer" as often as "Bearer".
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required"
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required"
        )

    return token.strip()


def verify_token(token: str):
    """Ask Supabase whether this token is real, unexpired and untampered."""
    try:
        result = supabase.auth.get_user(token)
    except AuthRetryableError:
        # Supabase itself is unreachable. That is our problem, not the caller's,
        # so it must not be reported as a bad token.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        )
    except AuthError:
        # Expired, tampered with, malformed, or already signed out.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    if result is None or result.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    return result.user


def require_auth(authorization: Optional[str] = Header(default=None)) -> AuthContext:
    """The guard itself: `Depends(require_auth)` protects a route."""
    token = extract_bearer_token(authorization)
    user = verify_token(token)
    return AuthContext(token=token, user=user)


def get_current_user(auth: AuthContext = Depends(require_auth)):
    """Convenience for routes that want the user and not the token."""
    return auth.user
