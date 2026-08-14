"""Routes that require a valid Supabase access token."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status
from supabase_auth.errors import AuthError, AuthRetryableError

from app.schemas import ErrorResponse
from app.supabase_client import supabase

router = APIRouter(prefix="/protected", tags=["protected"])


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


@router.get(
    "/profile",
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}},
    summary="Returns the verified caller's profile",
)
def profile(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    user = verify_token(token)

    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at,
        "last_sign_in_at": user.last_sign_in_at,
        "role": user.role,
    }
