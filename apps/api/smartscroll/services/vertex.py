"""Vertex AI service for Gemma 4 script rewriting."""

import asyncio
from functools import lru_cache

import structlog
import vertexai
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, GenerationConfig

from smartscroll.config import get_settings
from smartscroll.prompts.script_rewrite import (
    SCRIPT_PROMPT_V,
    SCRIPT_REWRITE_SYSTEM,
    SCRIPT_REWRITE_USER,
)

logger = structlog.get_logger()

# Gemma 4 26B MoE on Vertex AI Model Garden (serverless MaaS)
DEFAULT_GEMMA_MODEL = "gemma-4-26b-a4b-it-maas"


@lru_cache
def _init_vertex(location: str = "us-central1") -> None:
    """Initialize Vertex AI SDK once."""
    settings = get_settings()
    vertexai.init(
        project=settings.gcp_project_id,
        location=location,
    )
    aiplatform.init(
        project=settings.gcp_project_id,
        location=location,
    )


def _is_endpoint_id(value: str) -> bool:
    """Check if the value looks like a deployed endpoint ID (numeric) vs model name."""
    return value.isdigit() or value.startswith("projects/")


def _get_model() -> GenerativeModel:
    """Get the Gemma model instance for serverless Model Garden."""
    settings = get_settings()

    # Use configured model or default
    model_name = settings.vertex_gemma_endpoint or DEFAULT_GEMMA_MODEL

    # If it's an endpoint ID, we need to use the Endpoint class instead
    if _is_endpoint_id(model_name):
        raise ValueError(
            f"Deployed endpoint detected ({model_name}). "
            "Use call_deployed_endpoint() instead of GenerativeModel."
        )

    # Gemma 4 MaaS models require global endpoint
    if "maas" in model_name:
        _init_vertex(location="global")
    else:
        _init_vertex(location=settings.vertex_gemma_location)

    return GenerativeModel(
        model_name=model_name,
        system_instruction=SCRIPT_REWRITE_SYSTEM,
    )


def _get_deployed_endpoint() -> aiplatform.Endpoint:
    """Get a deployed Model Garden endpoint."""
    settings = get_settings()
    _init_vertex(location=settings.vertex_gemma_location)
    endpoint_id = settings.vertex_gemma_endpoint

    if not endpoint_id:
        raise ValueError("VERTEX_GEMMA_ENDPOINT must be set for deployed endpoints")

    return aiplatform.Endpoint(endpoint_id)


async def _call_serverless_model(prompt: str) -> str:
    """Call serverless Model Garden model (e.g., gemma-2-27b-it)."""
    model = _get_model()

    generation_config = GenerationConfig(
        max_output_tokens=512,
        temperature=0.7,
        top_p=0.9,
    )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(
            prompt,
            generation_config=generation_config,
        ),
    )
    return response.text.strip()


async def _call_deployed_endpoint(prompt: str) -> str:
    """Call a deployed Model Garden endpoint."""
    endpoint = _get_deployed_endpoint()

    # Format for Gemma instruction-tuned models
    full_prompt = f"{SCRIPT_REWRITE_SYSTEM}\n\n{prompt}"

    instances = [{"prompt": full_prompt}]
    parameters = {
        "max_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.9,
    }

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: endpoint.predict(instances=instances, parameters=parameters),
    )

    # Extract text from prediction response
    if response.predictions:
        return response.predictions[0].strip()
    raise ValueError("Empty response from endpoint")


async def rewrite_chunk_to_script(
    chunk_text: str,
    pdf_id: str,
    chunk_id: str,
) -> tuple[str, int]:
    """Rewrite a PDF chunk into a TikTok-style narration script.

    Args:
        chunk_text: The source text from the PDF chunk.
        pdf_id: PDF ID for logging.
        chunk_id: Chunk ID for logging.

    Returns:
        Tuple of (script_text, prompt_version).

    Raises:
        Exception: If Gemma API call fails.
    """
    settings = get_settings()
    log = logger.bind(pdf_id=pdf_id, chunk_id=chunk_id, step="script_rewrite")
    log.info("starting_script_rewrite", word_count=len(chunk_text.split()))

    prompt = SCRIPT_REWRITE_USER.format(chunk_text=chunk_text)

    # Route to appropriate backend
    endpoint_value = settings.vertex_gemma_endpoint or DEFAULT_GEMMA_MODEL
    if _is_endpoint_id(endpoint_value):
        log.info("using_deployed_endpoint", endpoint=endpoint_value)
        script = await _call_deployed_endpoint(prompt)
    else:
        log.info("using_serverless_model", model=endpoint_value)
        script = await _call_serverless_model(prompt)

    word_count = len(script.split())

    log.info(
        "script_rewrite_complete",
        output_word_count=word_count,
        prompt_version=SCRIPT_PROMPT_V,
    )

    return script, SCRIPT_PROMPT_V


async def check_vertex_connection() -> bool:
    """Check if Vertex AI is configured and accessible.

    Returns:
        True if connection successful, False otherwise.
    """
    try:
        settings = get_settings()
        if not settings.gcp_project_id:
            logger.warning("vertex_not_configured", reason="missing gcp_project_id")
            return False

        _init_vertex()
        # Just verify init works, don't make an actual call
        return True
    except Exception as e:
        logger.error("vertex_connection_failed", error=str(e))
        return False
