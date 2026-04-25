#!/usr/bin/env python3
"""
Test the video caption generation and rendering for a local PDF.

Reuses output/script.txt + output/narration.mp3 + output/timings.json
from a prior pipeline_local.py run so you don't redo TTS.
If those files don't exist, regenerates them from the PDF.

Usage:
    uv run python scripts/test_caption.py temp/deep_vol.pdf
    uv run python scripts/test_caption.py temp/deep_vol.pdf --regen-script
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

OUTPUT_DIR = Path("./output")


async def run(pdf_path: Path, regen_script: bool) -> None:
    from smartscroll.services.ingestion import extract_full_pdf_text
    from smartscroll.services.vertex import generate_video_caption, rewrite_pdf_to_script
    from smartscroll.services.tts import generate_speech_with_timestamps
    from smartscroll.pipeline.render import build_ass_captions
    from smartscroll.services.tts import WordTiming

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    script_file = OUTPUT_DIR / "script.txt"
    narration_file = OUTPUT_DIR / "narration.mp3"
    timings_file = OUTPUT_DIR / "timings.json"

    # ── Step 1: Script ────────────────────────────────────────────────────────
    if not regen_script and script_file.exists():
        script = script_file.read_text()
        print(f"[1/3] Reusing existing script ({len(script.split())} words) from {script_file}")
    else:
        print(f"[1/3] Extracting text and generating script from {pdf_path} ...")
        pdf_text = extract_full_pdf_text(str(pdf_path))
        script, version = await rewrite_pdf_to_script(pdf_text, pdf_id="caption_test")
        script_file.write_text(script)
        print(f"      Generated {len(script.split())} words (prompt v{version})")

    # ── Step 2: Caption ───────────────────────────────────────────────────────
    print("\n[2/3] Generating video caption with Gemma ...")
    caption = await generate_video_caption(script, pdf_id="caption_test")
    print(f"\n      ┌─ Caption ───────────────────────────────┐")
    print(f"      │  {caption}")
    print(f"      └─────────────────────────────────────────┘\n")

    # Save for inspection
    (OUTPUT_DIR / "caption.txt").write_text(caption)

    # ── Step 3: Render (if audio available) ──────────────────────────────────
    if not narration_file.exists() or not timings_file.exists():
        print("[3/3] narration.mp3 / timings.json not found — generating TTS ...")
        tts = await generate_speech_with_timestamps(script)
        narration_file.write_bytes(tts.audio)
        timings_data = [
            {"word": w.word, "start": w.start_time, "end": w.end_time}
            for w in tts.word_timings
        ]
        timings_file.write_text(json.dumps(timings_data, indent=2))
        print(f"      Generated {tts.duration_ms / 1000:.1f}s of audio")
        word_timings = tts.word_timings
        duration_ms = tts.duration_ms
    else:
        print(f"[3/3] Reusing existing audio from {narration_file}")
        raw = json.loads(timings_file.read_text())
        word_timings = [WordTiming(word=w["word"], start_time=w["start"], end_time=w["end"]) for w in raw]
        duration_ms = int(raw[-1]["end"] * 1000)

    # Write the .ass file so you can inspect the caption entry
    captions_path = OUTPUT_DIR / "captions.ass"
    build_ass_captions(word_timings, captions_path, video_caption=caption)
    print(f"      Caption burned into {captions_path}")

    # Local render (no GCS — output straight to output/video.mp4)
    print("\n      Rendering video locally (this takes ~1-2 min) ...")
    import ffmpeg
    import tempfile

    gameplay_candidates = list(Path("output").glob("gameplay*.mp4"))
    if not gameplay_candidates:
        print("\n      No gameplay*.mp4 found in output/ — skipping render.")
        print("      To render, copy a gameplay clip to output/gameplay.mp4 and rerun.")
        print("\nDone. Check output/caption.txt and output/captions.ass.")
        return

    gameplay_path = gameplay_candidates[0]
    output_path = OUTPUT_DIR / "video.mp4"
    duration_seconds = duration_ms / 1000

    from smartscroll.pipeline.render import OUTPUT_WIDTH, OUTPUT_HEIGHT

    try:
        gameplay = ffmpeg.input(str(gameplay_path), stream_loop=-1, t=duration_seconds)
        audio = ffmpeg.input(str(narration_file))
        video = (
            gameplay.video
            .filter("scale", OUTPUT_WIDTH, OUTPUT_HEIGHT, force_original_aspect_ratio="increase")
            .filter("crop", OUTPUT_WIDTH, OUTPUT_HEIGHT)
            .filter("ass", str(captions_path))
        )
        out = ffmpeg.output(
            video, audio.audio, str(output_path),
            vcodec="libx264", preset="fast", crf=23,
            acodec="aac", audio_bitrate="192k",
        )
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        size_mb = output_path.stat().st_size / 1_000_000
        print(f"      Rendered {size_mb:.1f} MB → {output_path}")
    except Exception as e:
        print(f"      Render failed: {e}")

    print("\nDone. Check output/caption.txt, output/captions.ass, output/video.mp4")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test caption generation and video render")
    parser.add_argument("pdf_path", nargs="?", default="temp/deep_vol.pdf")
    parser.add_argument("--regen-script", action="store_true",
                        help="Force re-generation of script even if output/script.txt exists")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found")
        sys.exit(1)

    asyncio.run(run(pdf_path, args.regen_script))


if __name__ == "__main__":
    main()
