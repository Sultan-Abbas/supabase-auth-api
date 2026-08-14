"""Reusable auth guard.

Every protected route depends on `require_auth`, so the header parsing and the
Supabase token check live in exactly one place. A route body only ever runs
after the token has been verified.
"""

from typing import Any, NamedTuple, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthError, AuthRetryableError

from app.supabase_client import supabase

# Declaring the scheme is what puts the padlock and the "Authorize" button in
# Swagger UI. auto_error=False keeps our own 401 body instead of FastAPI's
# {"detail": "Not authenticated"}.
bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    auto_error=False,
    description="Paste the access_token returned by POST /auth/login.",
)


class AuthContext(NamedTuple):
    """The verified user plus the raw token, which logout still needs."""

    token: str
    user: Any


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


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthContext:
    """The guard itself: `Depends(require_auth)` protects a route.

    HTTPBearer does the header parsing: a missing header, a non-Bearer scheme
    or an empty token all arrive here as None (it matches the scheme name
    case-insensitively, as RFC 7235 requires).
    """
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required"
        )

    token = credentials.credentials.strip()
    user = verify_token(token)
    return AuthContext(token=token, user=user)


def get_current_user(auth: AuthContext = Depends(require_auth)):
    """Convenience for routes that want the user and not the token."""
    return auth.user
