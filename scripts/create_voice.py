#!/usr/bin/env python3
"""
Create an ElevenLabs voice using Instant Voice Cloning (IVC).

Usage:
    uv run python scripts/create_voice.py temp/narrator.mp3 --name "SmartScroll Narrator"

The script will:
1. Upload the audio file to ElevenLabs
2. Create an instant voice clone
3. Print the voice_id (save this to ELEVENLABS_VOICE_ID in .env)
"""

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


def create_voice(
    audio_path: str,
    name: str,
    description: str | None = None,
    remove_background_noise: bool = False,
) -> dict:
    """
    Create an ElevenLabs voice using Instant Voice Cloning.

    Args:
        audio_path: Path to the audio file (mp3, wav, etc.)
        name: Name for the voice
        description: Optional description
        remove_background_noise: Whether to remove background noise

    Returns:
        dict with voice_id and other response data
    """
    load_dotenv()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not found in environment")

    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    url = "https://api.elevenlabs.io/v1/voices/add"

    headers = {
        "xi-api-key": api_key,
    }

    # Build form data
    data = {
        "name": name,
        "remove_background_noise": str(remove_background_noise).lower(),
    }
    if description:
        data["description"] = description

    # Read the audio file
    with open(audio_file, "rb") as f:
        files = {
            "files": (audio_file.name, f, "audio/mpeg"),
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, data=data, files=files)

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}", file=sys.stderr)
        response.raise_for_status()

    return response.json()


def main():
    parser = argparse.ArgumentParser(
        description="Create an ElevenLabs voice using Instant Voice Cloning"
    )
    parser.add_argument("audio_path", help="Path to the audio file (mp3, wav, etc.)")
    parser.add_argument("--name", required=True, help="Name for the voice")
    parser.add_argument("--description", help="Optional description for the voice")
    parser.add_argument(
        "--remove-noise",
        action="store_true",
        help="Remove background noise from the audio",
    )

    args = parser.parse_args()

    print(f"Creating voice from: {args.audio_path}")
    print(f"Voice name: {args.name}")

    result = create_voice(
        audio_path=args.audio_path,
        name=args.name,
        description=args.description,
        remove_background_noise=args.remove_noise,
    )

    print("\nVoice created successfully!")
    print(f"Voice ID: {result['voice_id']}")

    if result.get("requires_verification"):
        print("\nNote: This voice requires verification before use.")

    print("\nAdd this to your .env file:")
    print(f"ELEVENLABS_VOICE_ID={result['voice_id']}")


if __name__ == "__main__":
    main()
