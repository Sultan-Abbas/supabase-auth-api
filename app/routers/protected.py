"""Routes that require a valid Supabase access token.

Neither handler does any token work of its own: the `get_current_user`
dependency has already parsed the header and verified the token with Supabase
by the time these functions are entered.
"""

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.schemas import ErrorResponse

router = APIRouter(
    prefix="/protected",
    tags=["protected"],
    responses={401: {"model": ErrorResponse}},
)


@router.get(
    "/profile",
    status_code=status.HTTP_200_OK,
    summary="Returns the verified caller's profile",
)
def profile(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at,
        "last_sign_in_at": user.last_sign_in_at,
        "role": user.role,
    }


@router.get(
    "/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Second protected route, guarded by the same dependency",
)
def dashboard(user=Depends(get_current_user)):
    return {
        "message": f"Welcome back, {user.email}. This dashboard is yours alone.",
        "user_id": user.id,
    }
