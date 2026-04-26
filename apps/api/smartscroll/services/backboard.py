"""Backboard AI research + grading service."""

import json as _json
import re as _re

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


_JUDGE_SYSTEM = """\
You are a rigorous but fair academic grader. You will receive:
1. A short educational video script as context
2. An open-ended question
3. A 5-point rubric (each criterion is worth 1 point)
4. A student's answer

Evaluate the answer against every rubric criterion independently.
Output ONLY a valid JSON object with exactly two keys:
- "feedback": array of exactly 5 objects, each with:
    - "criterion": the rubric criterion string (copy it verbatim)
    - "hit": boolean — true if the answer satisfactorily addresses this criterion
    - "comment": one concise sentence explaining your judgement
- "score": integer 0–5 (must equal the count of "hit": true entries)

No markdown, no code fences, no extra text — raw JSON only.\
"""


async def judge_free_response(
    script: str,
    question: str,
    rubric: list[str],
    answer: str,
) -> dict:
    """Judge a free-response answer using a Backboard grading assistant.

    Returns {"score": int, "feedback": list[{"criterion", "hit", "comment"}]}.
    Raises on network/API failure — caller should handle gracefully.
    """
    settings = get_settings()
    if not settings.backboard_key:
        raise ValueError("BACKBOARD_KEY is not set")

    headers = {
        "X-API-Key": settings.backboard_key,
        "Content-Type": "application/json",
    }
    log = logger.bind(step="judge_fr")

    rubric_lines = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(rubric))
    user_message = (
        f"Video script context (first 2000 chars):\n{script[:2000]}\n\n"
        f"Question: {question}\n\n"
        f"Rubric (5 criteria):\n{rubric_lines}\n\n"
        f"Student's answer:\n{answer}"
    )

    async with httpx.AsyncClient(timeout=90.0) as client:
        log.info("backboard_creating_judge_assistant")
        resp = await client.post(
            f"{_BASE_URL}/assistants",
            headers=headers,
            json={"name": "SmartScroll Grader", "system_prompt": _JUDGE_SYSTEM},
        )
        resp.raise_for_status()
        assistant_id = resp.json()["assistant_id"]

        resp = await client.post(
            f"{_BASE_URL}/assistants/{assistant_id}/threads",
            headers=headers,
        )
        resp.raise_for_status()
        thread_id = resp.json()["thread_id"]

        resp = await client.post(
            f"{_BASE_URL}/threads/{thread_id}/messages",
            headers=headers,
            json={"content": user_message, "web_search": "Off", "memory": "Off", "stream": False},
        )
        resp.raise_for_status()
        raw = resp.json()["content"]

    log.info("backboard_judge_done")

    # Strip fences and parse
    raw = _re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    data = _json.loads(raw)

    feedback = []
    for item in (data.get("feedback") or [])[:5]:
        feedback.append({
            "criterion": str(item.get("criterion", "")),
            "hit": bool(item.get("hit", False)),
            "comment": str(item.get("comment", "")),
        })

    score = int(data.get("score", sum(1 for f in feedback if f["hit"])))
    score = max(0, min(5, score))

    return {"score": score, "feedback": feedback}
