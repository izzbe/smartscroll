"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smartscroll.routes import chat, feed, health, pdfs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown."""
    # TODO: Initialize logging, validate config
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SmartScroll API",
        description="TikTok-style AI-narrated PDF summaries",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(pdfs.router, prefix="/api/pdfs", tags=["pdfs"])
    app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

    return app


app = create_app()
