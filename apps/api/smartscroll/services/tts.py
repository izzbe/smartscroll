"""ElevenLabs TTS service with word-level timestamps."""

import base64
from dataclasses import dataclass

import httpx
import structlog

from smartscroll.config import get_settings

logger = structlog.get_logger()

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


@dataclass
class WordTiming:
    """Timing information for a single word."""

    word: str
    start_time: float  # seconds
    end_time: float  # seconds


@dataclass
class TTSResult:
    """Result from text-to-speech generation."""

    audio: bytes  # Raw audio bytes (MP3)
    word_timings: list[WordTiming]
    duration_ms: int  # Total duration in milliseconds


def _characters_to_words(
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
) -> list[WordTiming]:
    """Convert character-level timing to word-level timing.

    ElevenLabs returns timing for each character. This aggregates
    characters into words, using whitespace as delimiters.

    Args:
        characters: List of characters from the API response.
        start_times: Start time in seconds for each character.
        end_times: End time in seconds for each character.

    Returns:
        List of WordTiming objects for each word.
    """
    word_timings: list[WordTiming] = []
    current_word = ""
    word_start: float | None = None

    for i, char in enumerate(characters):
        if char.isspace():
            # End of word - save it if we have one
            if current_word and word_start is not None:
                word_timings.append(
                    WordTiming(
                        word=current_word,
                        start_time=word_start,
                        end_time=end_times[i - 1] if i > 0 else start_times[i],
                    )
                )
            current_word = ""
            word_start = None
        else:
            # Part of a word
            if word_start is None:
                word_start = start_times[i]
            current_word += char

    # Don't forget the last word
    if current_word and word_start is not None:
        word_timings.append(
            WordTiming(
                word=current_word,
                start_time=word_start,
                end_time=end_times[-1] if end_times else word_start,
            )
        )

    return word_timings


async def generate_speech_with_timestamps(
    text: str,
    voice_id: str | None = None,
    model_id: str = DEFAULT_MODEL,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    speed: float = 1.0,
) -> TTSResult:
    """Generate speech from text with word-level timestamps.

    Args:
        text: The text to convert to speech.
        voice_id: ElevenLabs voice ID. Defaults to ELEVENLABS_VOICE_ID from env.
        model_id: ElevenLabs model ID.
        stability: Voice stability (0-1). Lower = more expressive.
        similarity_boost: Voice similarity (0-1). Higher = closer to original.
        style: Style exaggeration (0-1). Higher = more stylized.
        speed: Speech speed multiplier.

    Returns:
        TTSResult with audio bytes and word timings.

    Raises:
        ValueError: If API key or voice ID not configured.
        httpx.HTTPStatusError: If API call fails.
    """
    settings = get_settings()
    api_key = settings.elevenlabs_api_key
    voice_id = voice_id or settings.elevenlabs_voice_id

    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not configured")
    if not voice_id:
        raise ValueError("ELEVENLABS_VOICE_ID not configured")

    log = logger.bind(voice_id=voice_id, text_length=len(text))
    log.info("generating_speech_with_timestamps")

    url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}/with-timestamps"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "speed": speed,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
            params={"output_format": DEFAULT_OUTPUT_FORMAT},
        )

    if response.status_code != 200:
        log.error(
            "elevenlabs_api_error",
            status_code=response.status_code,
            response=response.text[:500],
        )
        response.raise_for_status()

    data = response.json()

    # Decode audio from base64
    audio_bytes = base64.b64decode(data["audio_base64"])

    # Convert character timing to word timing
    alignment = data.get("alignment", {})
    characters = alignment.get("characters", [])
    start_times = alignment.get("character_start_times_seconds", [])
    end_times = alignment.get("character_end_times_seconds", [])

    word_timings = _characters_to_words(characters, start_times, end_times)

    # Calculate duration from the last end time
    duration_ms = int(end_times[-1] * 1000) if end_times else 0

    log.info(
        "speech_generated",
        duration_ms=duration_ms,
        word_count=len(word_timings),
        audio_bytes=len(audio_bytes),
    )

    return TTSResult(
        audio=audio_bytes,
        word_timings=word_timings,
        duration_ms=duration_ms,
    )


async def generate_speech(
    text: str,
    voice_id: str | None = None,
    model_id: str = DEFAULT_MODEL,
) -> bytes:
    """Generate speech from text (without timestamps).

    Simple wrapper when you just need the audio bytes.

    Args:
        text: The text to convert to speech.
        voice_id: ElevenLabs voice ID. Defaults to ELEVENLABS_VOICE_ID from env.
        model_id: ElevenLabs model ID.

    Returns:
        Raw audio bytes (MP3).
    """
    settings = get_settings()
    api_key = settings.elevenlabs_api_key
    voice_id = voice_id or settings.elevenlabs_voice_id

    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not configured")
    if not voice_id:
        raise ValueError("ELEVENLABS_VOICE_ID not configured")

    url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "text": text,
        "model_id": model_id,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
            params={"output_format": DEFAULT_OUTPUT_FORMAT},
        )

    response.raise_for_status()
    return response.content
