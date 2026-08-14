"""Routes that require a bearer token.

Stage 2 only checks that a token was *presented* in the Authorization header.
Verifying that token against Supabase comes in Stage 3.
"""

from fastapi import APIRouter, Header, HTTPException, status
from typing import Optional

from app.schemas import ErrorResponse

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


@router.get(
    "/profile",
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}},
    summary="Returns the caller's profile (token not verified yet)",
)
def profile(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)

    # Stage 3 replaces this with a real supabase.auth.get_user(token) lookup.
    return {
        "message": "Token received. Verification arrives in Stage 3.",
        "token_preview": f"{token[:8]}...",
    }
