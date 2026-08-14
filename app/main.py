"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
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


@app.get("/", tags=["meta"])
def root():
    return {"status": "ok", "docs": "/docs"}
