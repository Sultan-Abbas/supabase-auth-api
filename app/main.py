"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers import auth, protected, public
from app.supabase_client import supabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Touching the auth sub-client proves the SDK was initialised with the
    # values from .env before we accept any traffic.
    assert supabase.auth is not None
    print(f"Server running and connected to Supabase ({settings.supabase_url})")
    yield


app = FastAPI(
    title="Supabase Auth API",
    description="A small FastAPI service that delegates authentication to Supabase Auth.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return errors as {"error": "..."} instead of FastAPI's {"detail": "..."}."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """A malformed body is a Bad Request (400), not FastAPI's default 422."""
    return JSONResponse(status_code=400, content={"error": "Invalid request body"})


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(protected.router)


@app.get("/", tags=["meta"])
def root():
    return {"status": "ok", "docs": "/docs"}
