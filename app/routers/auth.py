"""Authentication routes backed by Supabase Auth."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from supabase_auth.errors import AuthApiError, AuthError

from app.dependencies import AuthContext, require_auth
from app.schemas import Credentials, ErrorResponse, LoginResponse, SignupResponse
from app.supabase_client import supabase

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_credentials(body: Credentials) -> tuple[str, str]:
    """Return (email, password) or raise a 400 if either one is missing."""
    email = (body.email or "").strip()
    password = body.password or ""
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required",
        )
    return email, password


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SignupResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Register a new user with Supabase Auth",
)
def signup(body: Credentials):
    email, password = _require_credentials(body)

    try:
        result = supabase.auth.sign_up({"email": email, "password": password})
    except AuthApiError as exc:
        # Weak password, malformed email, already registered, rate limited...
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)

    if result.user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Sign up failed"
        )

    return {"user": jsonable_encoder(result.user)}


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Exchange email + password for an access token",
)
def login(body: Credentials):
    email, password = _require_credentials(body)

    try:
        result = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthApiError:
        # Never echo Supabase's message here: it can reveal whether the address
        # exists or is merely unconfirmed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login credentials"
        )

    session = result.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login credentials"
        )

    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": session.token_type,
        "expires_at": session.expires_at,
        "user": jsonable_encoder(result.user),
    }


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
    summary="Revoke the caller's session (protected)",
)
def logout(auth: AuthContext = Depends(require_auth)):
    # This server keeps no session of its own, so `auth.sign_out()` would have
    # nothing to revoke. `admin.sign_out(jwt)` is the documented way to revoke
    # the refresh tokens belonging to the token the caller presented.
    try:
        supabase.auth.admin.sign_out(auth.token, "global")
    except AuthError:
        # The guard already proved the token was valid; a session that is
        # already gone still leaves the caller logged out, which is the point.
        pass

    return Response(status_code=status.HTTP_204_NO_CONTENT)
