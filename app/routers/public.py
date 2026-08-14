"""Routes that anyone can reach, no token required."""

from fastapi import APIRouter, status

router = APIRouter(prefix="/public", tags=["public"])


@router.get(
    "/info",
    status_code=status.HTTP_200_OK,
    summary="Open endpoint, no authentication needed",
)
def public_info():
    return {"message": "Welcome stranger! This info is public."}
