"""Video rendering — mux gameplay + narration + burned-in captions into final MP4."""

import asyncio
import hashlib
import tempfile
from pathlib import Path

import ffmpeg
import structlog
from google.cloud import storage as gcs

from smartscroll.config import get_settings
from smartscroll.services.tts import WordTiming

logger = structlog.get_logger()

WORDS_PER_CAPTION = 5
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920


def _seconds_to_ass_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    cs = int((s % 1) * 100)
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def build_ass_captions(word_timings: list[WordTiming], output_path: Path) -> None:
    """Write a TikTok-style .ass subtitle file from word-level timings."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {OUTPUT_WIDTH}\n"
        f"PlayResY: {OUTPUT_HEIGHT}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,"
        " Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle,"
        " Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # White bold text, black outline (5px), mid-center
        "Style: Default,Arial,70,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "1,0,0,0,100,100,0,0,1,5,2,5,40,40,0,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    lines = [header]
    for i in range(0, len(word_timings), WORDS_PER_CAPTION):
        chunk = word_timings[i : i + WORDS_PER_CAPTION]
        text = " ".join(w.word for w in chunk)
        start = _seconds_to_ass_ts(chunk[0].start_time)
        end = _seconds_to_ass_ts(chunk[-1].end_time)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

    output_path.write_text("".join(lines), encoding="utf-8")


def _pick_clip_name(client: gcs.Client, bucket_name: str, pdf_id: str) -> str:
    blobs = list(client.list_blobs(bucket_name))
    if not blobs:
        raise RuntimeError(f"No gameplay clips in gs://{bucket_name}/ — run seed_gameplay.py first")
    idx = int(hashlib.md5(pdf_id.encode()).hexdigest(), 16) % len(blobs)
    return blobs[idx].name


def _download_blob(client: gcs.Client, bucket_name: str, blob_name: str, local_path: Path) -> None:
    client.bucket(bucket_name).blob(blob_name).download_to_filename(str(local_path))


def _upload_video(client: gcs.Client, bucket_name: str, local_path: Path, blob_path: str) -> str:
    blob = client.bucket(bucket_name).blob(blob_path)
    blob.upload_from_filename(str(local_path), content_type="video/mp4")
    return f"gs://{bucket_name}/{blob_path}"


def _run_ffmpeg(
    gameplay_path: Path,
    narration_path: Path,
    captions_path: Path,
    output_path: Path,
    duration_seconds: float,
) -> None:
    gameplay = ffmpeg.input(str(gameplay_path), stream_loop=-1, t=duration_seconds)
    audio = ffmpeg.input(str(narration_path))

    video = (
        gameplay.video
        .filter("scale", OUTPUT_WIDTH, OUTPUT_HEIGHT, force_original_aspect_ratio="increase")
        .filter("crop", OUTPUT_WIDTH, OUTPUT_HEIGHT)
        .filter("ass", str(captions_path))
    )

    out = ffmpeg.output(
        video,
        audio.audio,
        str(output_path),
        vcodec="libx264",
        preset="fast",
        crf=23,
        acodec="aac",
        audio_bitrate="192k",
    )

    try:
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else "no stderr"
        raise RuntimeError(f"FFmpeg render failed:\n{stderr}") from e


async def render_video(
    uid: str,
    pdf_id: str,
    narration_audio: bytes,
    word_timings: list[WordTiming],
    duration_ms: int,
) -> str:
    """
    Render final MP4: random gameplay clip + narration + burned-in captions.

    Returns:
        GCS URI of the rendered video (gs://smartscroll-rendered/...).
    """
    settings = get_settings()
    client = gcs.Client()
    loop = asyncio.get_event_loop()
    log = logger.bind(uid=uid, pdf_id=pdf_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        log.info("render_picking_clip")
        clip_name = await loop.run_in_executor(
            None, _pick_clip_name, client, settings.gcs_bucket_gameplay, pdf_id
        )
        gameplay_path = tmp / "gameplay.mp4"
        log.info("render_downloading_clip", clip=clip_name)
        await loop.run_in_executor(
            None, _download_blob, client, settings.gcs_bucket_gameplay, clip_name, gameplay_path
        )

        narration_path = tmp / "narration.mp3"
        narration_path.write_bytes(narration_audio)

        captions_path = tmp / "captions.ass"
        build_ass_captions(word_timings, captions_path)
        caption_cues = (len(word_timings) + WORDS_PER_CAPTION - 1) // WORDS_PER_CAPTION
        log.info("render_captions_built", cues=caption_cues)

        output_path = tmp / "output.mp4"
        duration_seconds = duration_ms / 1000
        log.info("render_ffmpeg_start", duration_s=round(duration_seconds, 1))
        await loop.run_in_executor(
            None,
            _run_ffmpeg,
            gameplay_path,
            narration_path,
            captions_path,
            output_path,
            duration_seconds,
        )
        size_mb = output_path.stat().st_size / 1_000_000
        log.info("render_ffmpeg_done", size_mb=round(size_mb, 1))

        blob_path = f"{uid}/{pdf_id}/video.mp4"
        video_gcs_uri = await loop.run_in_executor(
            None, _upload_video, client, settings.gcs_bucket_rendered, output_path, blob_path
        )
        log.info("render_uploaded", gcs_uri=video_gcs_uri)

    return video_gcs_uri
