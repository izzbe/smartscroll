#!/usr/bin/env python3
"""
Run the full ingest pipeline on a local PDF for debugging.

This script processes a PDF through text extraction, script generation,
and TTS without requiring GCS or Firestore. Useful for testing the core
pipeline logic locally.

Usage:
    uv run python scripts/pipeline_local.py path/to/paper.pdf [--output-dir ./output]

Output:
    - Extracted text printed to console
    - Generated script saved to {output_dir}/script.txt
    - Generated audio saved to {output_dir}/narration.mp3
    - Word timings saved to {output_dir}/timings.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add the apps/api directory to the path so we can import smartscroll
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


async def run_pipeline(pdf_path: str, output_dir: Path, skip_tts: bool = False) -> None:
    """Run the pipeline on a local PDF."""
    from smartscroll.services.ingestion import extract_full_pdf_text
    from smartscroll.services.vertex import rewrite_pdf_to_script

    print(f"\n{'='*60}")
    print(f"SmartScroll Local Pipeline")
    print(f"{'='*60}")
    print(f"Input: {pdf_path}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract text
    print("[1/4] Extracting text from PDF...")
    try:
        pdf_text = extract_full_pdf_text(pdf_path)
        word_count = len(pdf_text.split())
        print(f"      Extracted {word_count} words")

        # Save extracted text
        text_file = output_dir / "extracted_text.txt"
        text_file.write_text(pdf_text)
        print(f"      Saved to {text_file}")
    except Exception as e:
        print(f"      ERROR: {e}")
        sys.exit(1)

    # Step 2: Generate script with Gemma
    print("\n[2/4] Generating script with Gemma...")
    try:
        script, prompt_version = await rewrite_pdf_to_script(
            pdf_text=pdf_text,
            pdf_id="local_test",
        )
        script_word_count = len(script.split())
        print(f"      Generated {script_word_count} words (prompt v{prompt_version})")

        # Save script
        script_file = output_dir / "script.txt"
        script_file.write_text(script)
        print(f"      Saved to {script_file}")

        # Print script preview
        print(f"\n      --- Script Preview (first 500 chars) ---")
        print(f"      {script[:500]}...")
        print(f"      --- End Preview ---\n")
    except Exception as e:
        print(f"      ERROR: {e}")
        print("      Make sure VERTEX_GEMMA_ENDPOINT and GCP_PROJECT_ID are set in .env")
        sys.exit(1)

    # Step 3: Generate TTS
    if skip_tts:
        print("\n[3/4] Skipping TTS generation (--skip-tts)")
        print("\n[4/4] Skipping (no TTS)")
    else:
        print("\n[3/4] Generating TTS with ElevenLabs...")
        try:
            from smartscroll.services.tts import generate_speech_with_timestamps

            tts_result = await generate_speech_with_timestamps(script)
            duration_sec = tts_result.duration_ms / 1000
            print(f"      Generated {duration_sec:.1f}s of audio")
            print(f"      {len(tts_result.word_timings)} words with timestamps")

            # Save audio
            audio_file = output_dir / "narration.mp3"
            audio_file.write_bytes(tts_result.audio)
            print(f"      Saved to {audio_file}")

            # Save timings as JSON
            timings_file = output_dir / "timings.json"
            timings_data = [
                {
                    "word": wt.word,
                    "start": wt.start_time,
                    "end": wt.end_time,
                }
                for wt in tts_result.word_timings
            ]
            timings_file.write_text(json.dumps(timings_data, indent=2))
            print(f"      Timings saved to {timings_file}")

        except Exception as e:
            print(f"      ERROR: {e}")
            print("      Make sure ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are set in .env")
            sys.exit(1)

        # Step 4: Summary
        print(f"\n[4/4] Pipeline complete!")

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Input words:  {word_count}")
    print(f"  Script words: {script_word_count}")
    if not skip_tts:
        print(f"  Audio length: {duration_sec:.1f}s")
    print(f"  Output dir:   {output_dir}")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the SmartScroll pipeline on a local PDF"
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Skip TTS generation (useful for testing text extraction and script generation only)",
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    if not pdf_path.suffix.lower() == ".pdf":
        print(f"Error: File must be a PDF: {pdf_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)

    asyncio.run(run_pipeline(str(pdf_path), output_dir, args.skip_tts))


if __name__ == "__main__":
    main()
