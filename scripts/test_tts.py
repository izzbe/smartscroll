#!/usr/bin/env python3
"""Test the ElevenLabs TTS service with timestamps."""

import asyncio
import sys
from pathlib import Path

# Add the apps/api directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from dotenv import load_dotenv

load_dotenv()

from smartscroll.services.tts import generate_speech_with_timestamps


async def main():
    text = (
        "Here's the thing about machine learning that most people get wrong. "
        "It's not about the algorithms. It's about the data. "
        "And that changes everything."
    )

    print(f"Generating speech for: {text[:50]}...")
    print()

    # Use Rachel (default voice) for testing, or your custom voice if verified
    test_voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    result = await generate_speech_with_timestamps(text, voice_id=test_voice_id)

    print(f"Audio size: {len(result.audio):,} bytes")
    print(f"Duration: {result.duration_ms}ms ({result.duration_ms / 1000:.2f}s)")
    print(f"Word count: {len(result.word_timings)}")
    print()

    print("Word timings:")
    for wt in result.word_timings:
        print(f"  {wt.start_time:6.3f}s - {wt.end_time:6.3f}s: {wt.word}")

    # Save the audio to a file for manual verification
    output_path = Path("temp/test_tts_output.mp3")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_bytes(result.audio)
    print(f"\nAudio saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
