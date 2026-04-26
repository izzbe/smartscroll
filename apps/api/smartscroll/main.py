"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smartscroll.pipeline.render import warm_gameplay_cache
from smartscroll.routes import chat, feed, health, messages, pdfs, quiz, topics, users


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    asyncio.create_task(warm_gameplay_cache())
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
        allow_origins=[
            "http://localhost:3000",  # Next.js / legacy
            "http://localhost:5173",  # Vite dev server
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(pdfs.router, prefix="/api/pdfs", tags=["pdfs"])
    app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(topics.router, prefix="/api/topics", tags=["topics"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
    app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])

    return app


app = create_app()
