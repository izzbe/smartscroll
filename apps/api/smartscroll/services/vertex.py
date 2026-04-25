"""Vertex AI service for Gemma 4 script rewriting."""

import asyncio
from functools import lru_cache

import httpx
import structlog
import vertexai
from google.auth import default
from google.auth.transport.requests import Request
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
# MaaS models require the global endpoint
DEFAULT_GEMMA_MODEL = "google/gemma-4-26b-a4b-it-maas"


@lru_cache
def _get_credentials():
    """Get and cache Google Cloud credentials with Vertex AI scopes."""
    credentials, project = default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    return credentials


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


def _is_maas_model(model_name: str) -> bool:
    """Check if this is a MaaS model that requires the global endpoint."""
    return "maas" in model_name.lower()


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


async def _call_maas_model(prompt: str, model_name: str) -> str:
    """Call MaaS model via the global endpoint REST API.

    MaaS models like Gemma 4 require the global endpoint which isn't
    supported by the standard SDK, so we call the REST API directly.
    """
    settings = get_settings()
    credentials = _get_credentials()

    # Ensure credentials are fresh
    if credentials.expired:
        credentials.refresh(Request())

    # Global endpoint URL for MaaS models
    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{settings.gcp_project_id}"
        f"/locations/global/publishers/google/models/{model_name.split('/')[-1]}"
        f":generateContent"
    )

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{SCRIPT_REWRITE_SYSTEM}\n\n{prompt}"}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 4096,
            "temperature": 0.7,
            "topP": 0.9,
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        logger.error(
            "maas_api_error",
            status_code=response.status_code,
            response=response.text[:500],
        )
        response.raise_for_status()

    data = response.json()

    # Extract text from response
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No candidates in MaaS model response")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("No content parts in MaaS model response")

    return parts[0].get("text", "").strip()


async def _call_serverless_model(prompt: str) -> str:
    """Call serverless Model Garden model (e.g., gemma-2-27b-it)."""
    model = _get_model()

    generation_config = GenerationConfig(
        max_output_tokens=4096,  # Allow longer scripts for full PDFs
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
        "max_tokens": 4096,  # Allow longer scripts for full PDFs
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


async def rewrite_pdf_to_script(
    pdf_text: str,
    pdf_id: str,
) -> tuple[str, int]:
    """Rewrite an entire PDF into a TikTok-style narration script.

    Args:
        pdf_text: The full extracted text from the PDF.
        pdf_id: PDF ID for logging.

    Returns:
        Tuple of (script_text, prompt_version).

    Raises:
        Exception: If Gemma API call fails.
    """
    settings = get_settings()
    log = logger.bind(pdf_id=pdf_id, step="script_rewrite")
    log.info("starting_script_rewrite", word_count=len(pdf_text.split()))

    prompt = SCRIPT_REWRITE_USER.format(pdf_text=pdf_text)

    # Route to appropriate backend
    endpoint_value = settings.vertex_gemma_endpoint or DEFAULT_GEMMA_MODEL
    if _is_endpoint_id(endpoint_value):
        log.info("using_deployed_endpoint", endpoint=endpoint_value)
        script = await _call_deployed_endpoint(prompt)
    elif _is_maas_model(endpoint_value):
        log.info("using_maas_model", model=endpoint_value)
        script = await _call_maas_model(prompt, endpoint_value)
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
