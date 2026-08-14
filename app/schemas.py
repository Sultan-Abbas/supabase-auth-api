"""Request and response models.

The credential fields are deliberately optional so that a missing field reaches
the route handler and can be answered with a 400, instead of FastAPI's default
422 validation response.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    email: Optional[str] = Field(default=None, examples=["test@example.com"])
    password: Optional[str] = Field(default=None, examples=["password123"])


class ErrorResponse(BaseModel):
    error: str


class SignupResponse(BaseModel):
    user: dict[str, Any]


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: Optional[int] = None
    user: dict[str, Any]
