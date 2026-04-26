"""Backboard AI research service — topic → research article via web search + memory."""

import httpx
import structlog

from smartscroll.config import get_settings

logger = structlog.get_logger()

_BASE_URL = "https://app.backboard.io/api"

_RESEARCH_SYSTEM_PROMPT = (
    "You are a research assistant that produces comprehensive, accurate research articles on any "
    "topic. Given a topic or question, use web search to gather up-to-date information and produce "
    "a thorough article covering: key concepts, how it works, real-world applications, recent "
    "developments, and important nuances or common misconceptions. Write in clear, detailed prose — "
    "the article will be used as source material for a TikTok-style educational video, so depth and "
    "factual accuracy are essential. Aim for 400–700 words of dense, informative content."
)


async def research_topic(topic: str) -> str:
    """Research a topic using Backboard's agent with live web search and memory.

    Creates a fresh assistant + thread per call so each video gets an independent
    research context. Memory="Auto" lets Backboard extract and store key facts for
    future personalisation.

    Args:
        topic: Natural-language question or subject (e.g. "What is Redis?").

    Returns:
        Research article as plain text, ready to feed into Gemma script rewriting.

    Raises:
        ValueError: BACKBOARD_KEY missing from environment.
        httpx.HTTPStatusError: Backboard API returned a non-2xx response.
    """
    settings = get_settings()
    if not settings.backboard_key:
        raise ValueError("BACKBOARD_KEY is not set — add it to .env")

    headers = {
        "X-API-Key": settings.backboard_key,
        "Content-Type": "application/json",
    }
    log = logger.bind(topic=topic[:80])

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Create a dedicated research assistant
        log.info("backboard_creating_assistant")
        resp = await client.post(
            f"{_BASE_URL}/assistants",
            headers=headers,
            json={"name": "SmartScroll Research", "system_prompt": _RESEARCH_SYSTEM_PROMPT},
        )
        resp.raise_for_status()
        assistant_id = resp.json()["assistant_id"]

        # 2. Open a conversation thread
        resp = await client.post(
            f"{_BASE_URL}/assistants/{assistant_id}/threads",
            headers=headers,
        )
        resp.raise_for_status()
        thread_id = resp.json()["thread_id"]
        log.info("backboard_thread_ready", assistant_id=assistant_id, thread_id=thread_id)

        # 3. Send the topic; enable web search + automatic memory extraction
        resp = await client.post(
            f"{_BASE_URL}/threads/{thread_id}/messages",
            headers=headers,
            json={
                "content": topic,
                "web_search": "Auto",
                "memory": "Auto",
                "stream": False,
            },
        )
        resp.raise_for_status()
        research_text: str = resp.json()["content"]

    log.info("backboard_research_done", words=len(research_text.split()))
    return research_text
