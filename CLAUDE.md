# SmartScroll

> **One-liner:** TikTok-style infinite scroll where every video is an AI-narrated summary of a PDF the user uploaded, played over Subway Surfers / Minecraft parkour gameplay with burned-in captions. Longer-form productive brainrot.

This file is the source of truth for how to work in this repo. Read it before doing anything. If something here is wrong, fix it here first, then change the code.

---

## 1. Hackathon constraints (non-negotiable)

These are fixed. Do not propose alternatives unless explicitly asked.

| Layer | Choice | Why |
|---|---|---|
| Cloud | **GCP** | Free credits |
| LLM | **Gemma 4** (26B MoE on Vertex AI Model Garden, serverless) | Required |
| TTS | **ElevenLabs** | Required |
| Backend | **Python 3.12 + FastAPI** | Team expertise |
| Repo | **Monorepo** (`apps/web`, `apps/api`, `packages/shared`) | One deploy story |

**Default-but-changeable picks** (flag if you want to revisit):

- **Frontend**: Next.js 15 (App Router) + Tailwind. Deployed on Cloud Run.
- **DB**: Firestore for app data (users, pdfs, chunks, videos). BigQuery for analytics events only (views, skips, watch_ms).
- **Auth**: Firebase Auth (email/password to satisfy the spec, with Google OAuth as a freebie).
- **Object storage**: GCS — buckets `smartscroll_pdfs`, `smartscroll-gameplay`, `smartscroll-rendered`.
- **Job runner**: FastAPI `BackgroundTasks` for the hackathon. Cloud Tasks + a separate Cloud Run worker is the upgrade path; do NOT build that now.
- **Transcription/timestamps**: ElevenLabs TTS with timestamps API (returns word-level timing with audio generation — no separate Whisper step needed).
- **Video muxing**: FFmpeg via `ffmpeg-python`. Captions burned in via `subtitles` filter from a generated `.ass` file.

---

## 2. Repo layout

```
smartscroll/
├── apps/
│   ├── web/            # Next.js 15, vertical-scroll feed UI
│   └── api/            # FastAPI, ingestion pipeline + feed endpoint
├── packages/
│   └── shared/         # Pydantic models + TS types (generated from Pydantic via datamodel-code-generator)
├── infra/
│   ├── terraform/      # GCS buckets, Firestore, IAM. Optional for hackathon.
│   └── docker/         # Dockerfiles for api + web
├── scripts/
│   ├── create_voice.py     # Create ElevenLabs voice via Instant Voice Cloning
│   ├── pipeline_local.py   # Run the full ingest pipeline on a local PDF for debugging
│   ├── seed_gameplay.py    # One-time: download N gameplay clips into GCS
│   └── test_tts.py         # Test TTS service with word timestamps
├── .env.example
├── CLAUDE.md           # this file
└── README.md           # human-facing setup
```

Always put new code in the right app. Shared types go in `packages/shared` — never copy a Pydantic model into the frontend; generate it.

---

## 3. The pipeline (the heart of the app)

Ingestion runs when a user uploads a PDF. One PDF = one video (no chunking):

```
PDF upload
  └─> [1] Extract full text (PyMuPDF) + structural hints (headings, page breaks)
  └─> [2] Gemma 4 → rewrite entire PDF into a TikTok-voice script (see §3.2 for prompt rules)
  └─> [3] ElevenLabs TTS with timestamps → narration MP3 + word-level timing (single API call)
  └─> [4] Upload narration MP3 to gs://smartscroll-rendered/{uid}/{pdf_id}/narration.mp3
  └─> [5] Pick a random gameplay clip from gs://smartscroll-gameplay/ (deterministic: md5(pdf_id) % n)
  └─> [6] Generate .ass subtitle file from word timestamps (TikTok-style: 5 words per cue, centered)
  └─> [7] FFmpeg: loop gameplay to audio length, scale/crop to 1080×1920, burn captions → MP4
  └─> [8] Upload final MP4 to gs://smartscroll-rendered/{uid}/{pdf_id}/video.mp4
  └─> [9] Write video metadata to Firestore (video_gcs_path set). Mark PDF status = ready.
```

### 3.1 Full-PDF processing

The entire PDF is processed as a single unit. Gemma 4 receives the full extracted text and produces one cohesive script that covers the key points of the document.

**LLM-assisted handling:**
- Equations, code blocks, or figures detected → Gemma decides whether to skip, paraphrase, or describe.
- Very long PDFs (>10k words) → Gemma focuses on the most important concepts and findings.

The script should be **self-contained** — the viewer needs full context without having read the PDF.

### 3.2 Script rewriting (the Gemma prompt)

The script is the make-or-break of the app. Hard rules baked into the system prompt:

- **No strict word limit.** Let the script be as long as needed to cover the PDF's key points. Longer PDFs = longer videos.
- **Hook in the first 8 words.** "Here's why X is wild:" / "Most people get Y completely wrong:" / "There's a study that…"
- **Conversational, second-person, present tense.** No "the author argues." Yes "so basically what they found is…"
- **No filler intros** ("In this video we'll explore…"). Drop straight into the content.
- **End on a payoff or a cliffhanger**, never a summary.
- **Plain text only.** No markdown, no headers, no bullets — this gets fed to TTS.

Keep the prompt in `apps/api/smartscroll/prompts/script_rewrite.py` as a single source of truth. Version it (`SCRIPT_PROMPT_V = 3`) and log the version with each generated video so we can A/B.

### 3.3 What the LLM is NOT for

- Don't use Gemma to pick gameplay clips. Random with seed = pdf_id is fine.
- Don't use Gemma to score/rank the feed. Use the deterministic algorithm in §5.
- Don't use Gemma for OCR. PyMuPDF handles text extraction; if the PDF is scanned, fall back to Vertex Document AI, not Gemma.

---

## 4. Data model (Firestore)

```
users/{uid}
  email, displayName, createdAt

users/{uid}/pdfs/{pdfId}
  filename, gcsPath, status: "uploading"|"processing"|"ready"|"failed",
  uploadedAt, errorMessage?

videos/{videoId}     # one video per PDF, denormalized for fast feed reads
  uid, pdfId, videoGcsPath, durationMs,
  script, scriptPromptVersion, wordCount,
  createdAt, viewCount, totalWatchMs
```

**Rule:** the feed endpoint reads from `videos/` only. One PDF = one video. No chunking.

---

## 5. The feed algorithm

For the hackathon, keep it simple and explainable. `GET /api/feed?cursor=...` returns 10 videos for the calling user.

```
candidates = videos where uid == current_user
score(v) = 0.7 * recency_decay(v.createdAt, half_life=2_days)
        + 0.3 * (1 - normalized_view_count(v))
shuffle within score buckets (don't return strict ordering — feels deterministic and boring)
```

No cross-user discovery for v1. If the demo needs it, we'll add a `public: bool` flag and a separate global feed.

---

## 6. Frontend — the scroll

- One video on screen at a time, full-viewport, snap-scroll vertical.
- Use the `IntersectionObserver` API + `<video>` with `playsInline muted autoplay loop`.
  - Start muted (browser autoplay policy). Tap-to-unmute on first interaction, then remember preference.
- **Preload the next 2 videos** (HTML `preload="auto"` on the next two `<video>` tags, hidden). Anything more wastes bandwidth.
- Log `view` (>=1s watched) and `complete` (>=90% watched) events to `/api/events`. Batch client-side, flush every 5s or on visibility change.
- **No infinite scroll without an end state.** When the user runs out of their videos, show "Upload more PDFs" CTA. Don't loop silently — that's confusing.

Mobile-first CSS even though it's a web app. Design at 390×844 (iPhone 14) and let it letterbox on desktop.

---

## 7. Environment variables

All secrets live in `.env` locally and Secret Manager in prod. **Never hardcode, never commit.** `.env.example` must stay in sync — if you add a var, add it there too.

```
# GCP
GCP_PROJECT_ID=
GCP_REGION=us-central1
GCS_BUCKET_PDFS=smartscroll_pdfs
GCS_BUCKET_GAMEPLAY=smartscroll-gameplay
GCS_BUCKET_RENDERED=smartscroll-rendered
GOOGLE_APPLICATION_CREDENTIALS=./gcp-sa.json   # local only

# Vertex AI / Gemma 4
VERTEX_GEMMA_ENDPOINT=         # Leave empty for default MaaS model, or set endpoint ID
VERTEX_GEMMA_LOCATION=us-central1

# Firebase (frontend)
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=

# Firebase Admin (backend)
FIREBASE_ADMIN_CREDENTIALS_JSON=  # base64-encoded service account

# ElevenLabs
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=              # default narrator voice
```

---

## 8. Local dev

```bash
# Install Python deps (from repo root — pyproject.toml is at root level)
uv sync

# Run API server
uv run uvicorn smartscroll.main:app --reload --port 8000

# Frontend
cd apps/web
pnpm install
pnpm dev   # localhost:3000

# Run the full pipeline on a local PDF without the API
uv run python scripts/pipeline_local.py path/to/paper.pdf
```

`config.py` reads `GOOGLE_APPLICATION_CREDENTIALS` directly from `.env` and injects it into `os.environ` at startup, so no shell prefix is needed. If you need to override with a different key (e.g. for a different GCP project), set it on the command line: `GOOGLE_APPLICATION_CREDENTIALS=./other-key.json uv run ...`

Use **uv** for Python (not pip, not poetry). Use **pnpm** for JS (not npm). Don't switch package managers — lockfile churn ruins hackathons.

`pipeline_local.py` is the most useful script in this repo. If you're debugging the pipeline, run that, not the full server.

---

## 9. Conventions Claude should follow

- **Types over guesses.** Pydantic models for every API boundary. No `dict[str, Any]` in function signatures.
- **Async everywhere in the API.** Don't mix sync GCS/Firestore calls into async handlers — use `google-cloud-storage` async clients or `run_in_executor`.
- **One file per concept** in `apps/api/smartscroll/`. e.g. `pipeline/chunk.py`, `pipeline/script.py`, `pipeline/tts.py`, `pipeline/caption.py`, `pipeline/render.py`. Don't write a 1000-line `pipeline.py`.
- **Log structured JSON** (`structlog`). Every pipeline step logs `pdf_id`, `chunk_id`, `step`, `duration_ms`. We will need this when something is slow at demo time.
- **Fail loud in dev, fail soft in prod.** A failed chunk should mark itself `failed` in Firestore and not block sibling chunks.
- **No new dependencies without justification.** If you're tempted to add a library, check if `httpx`, `pydantic`, `ffmpeg-python`, or stdlib already does it.
- **Prefer SQL-style explicit queries over ORM magic.** We're on Firestore, so this mostly means: write the filter, don't fetch-then-filter-in-Python.

---

## 10. Anti-patterns (do not do)

- ❌ Don't add Redis, Celery, RabbitMQ, Kafka. We have a hackathon deadline.
- ❌ Don't fetch YouTube videos at request time. Gameplay clips are pre-seeded once via `scripts/seed_gameplay.py`.
- ❌ Don't generate captions with Gemma. Use ElevenLabs word timestamps. Gemma hallucinates timing.
- ❌ Don't render videos client-side. Pre-render server-side at upload, store final MP4, stream it.
- ❌ Don't use `setInterval` to poll for upload status in the frontend. Use a Firestore real-time listener on the PDF doc.
- ❌ Don't put the ElevenLabs key in the frontend. All TTS calls go through `/api/tts` if ever exposed (they shouldn't be — TTS only runs server-side during ingestion).
- ❌ Don't try to make the feed "smart" with embeddings/vectors for v1. Recency + shuffle is fine and demos well.

---

## 11. Demo-day checklist (read 24h before)

- [ ] Seed gameplay bucket with at least 10 clips (Subway Surfers, Minecraft parkour, Trackmania, Temple Run).
- [ ] Pre-process 3 "showcase" PDFs (one ML paper, one textbook chapter, one blog post) so the feed isn't empty on a fresh demo account.
- [ ] Test the full pipeline end-to-end on a fresh PDF in <90s. If it's slower, profile `render` step first — FFmpeg is usually the culprit.
- [ ] Have a backup video file ready in case Vertex/ElevenLabs goes down mid-demo.
- [ ] Disable any debug logging that prints PDFs to stdout.

---

## 12. When in doubt

- **Pick the boring option.** Hackathon ≠ portfolio piece.
- **If a step takes >30 min to figure out, ask the team.** Don't burn an hour on IAM.
- **Show, don't perfect.** A demo where 80% works and 20% is hardcoded beats one where everything is real but the script LLM is still being prompt-engineered at 3am.

---

## 13. Implementation status

### Completed
- [x] **PDF upload to GCS** — `POST /api/pdfs/upload` uploads to `gs://smartscroll_pdfs/{uid}/{pdf_id}/{filename}`
- [x] **Firestore persistence** — PDFs stored in `users/{uid}/pdfs/{pdfId}`, database ID: `smartscroll`
- [x] **List PDFs** — `GET /api/pdfs` returns all PDFs for current user
- [x] **Get PDF** — `GET /api/pdfs/{pdf_id}` returns single PDF with status

### Not started
- [ ] Feed endpoint
- [ ] Frontend

### Completed (services)
- [x] **PDF text extraction** — `services/ingestion.py` extracts full text with PyMuPDF
- [x] **Gemma 4 script rewriting** — `services/vertex.py` rewrites PDF text into TikTok-style scripts
- [x] **ElevenLabs TTS with timestamps** — `services/tts.py` generates speech + word-level timing in one call
- [x] **Voice cloning script** — `scripts/create_voice.py` creates custom voices via IVC
- [x] **Video rendering** — `pipeline/render.py` picks gameplay clip, builds .ass captions, runs FFmpeg, uploads MP4
- [x] **Gameplay seeding** — `scripts/seed_gameplay.py` downloads 4 YouTube clips at 1080p into GCS
- [x] **Pipeline orchestrator** — `pipeline/orchestrator.py` connects all services end-to-end (PDF → MP4)
- [x] **Background processing** — Upload endpoint triggers async pipeline via FastAPI BackgroundTasks

---

## 14. API reference

Base URL: `http://localhost:8000`

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{"status": "healthy"}` |

### PDFs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/pdfs` | List all PDFs for current user |
| GET | `/api/pdfs/{pdf_id}` | Get single PDF by ID |
| POST | `/api/pdfs/upload` | Upload a PDF file |

#### `GET /api/pdfs`

List all PDFs for the current user from Firestore.

**Response:**
```json
{
  "uid": "user_demo_123",
  "pdfs": [
    {
      "pdf_id": "312325125f42470982144db2108f7acb",
      "filename": "deep_vol.pdf",
      "gcs_path": "gs://smartscroll_pdfs/user_demo_123/.../deep_vol.pdf",
      "status": "uploading",
      "error_message": null
    }
  ]
}
```

**Test:**
```bash
curl http://localhost:8000/api/pdfs
```

#### `GET /api/pdfs/{pdf_id}`

Get a single PDF by ID.

**Response:**
```json
{
  "pdf_id": "312325125f42470982144db2108f7acb",
  "filename": "deep_vol.pdf",
  "gcs_path": "gs://smartscroll_pdfs/user_demo_123/.../deep_vol.pdf",
  "status": "uploading",
  "error_message": null
}
```

**Errors:**
- `404` — PDF not found

**Test:**
```bash
curl http://localhost:8000/api/pdfs/{pdf_id}
```

#### `POST /api/pdfs/upload`

Upload a PDF to GCS, create Firestore record, and start background processing.
Associates with current user (dummy `user_demo_123` for now).

Background processing pipeline:
1. Extract text from PDF (PyMuPDF)
2. Generate TikTok-style script (Gemma 4)
3. Generate narration audio (ElevenLabs TTS)
4. Create video record in Firestore

Poll `GET /api/pdfs/{pdf_id}` to check status (`uploading` → `processing` → `ready` or `failed`).

**Request:**
```
Content-Type: multipart/form-data
file: <pdf file>
```

**Response:**
```json
{
  "pdf_id": "312325125f42470982144db2108f7acb",
  "uid": "user_demo_123",
  "gcs_uri": "gs://smartscroll_pdfs/user_demo_123/.../deep_vol.pdf",
  "filename": "deep_vol.pdf",
  "status": "uploading"
}
```

**Errors:**
- `400` — Not a PDF, file too large (>50MB), or empty file

**Test:**
```bash
curl -X POST http://localhost:8000/api/pdfs/upload -F "file=@temp/deep_vol.pdf"
```

### Feed (TODO)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/feed` | Get paginated video feed |

### Events (TODO)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/events` | Log view/complete events |

---

## 15. Project structure

```
smartscroll/
├── pyproject.toml              # Root — all Python deps here
├── apps/api/smartscroll/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Settings from env vars
│   ├── models/
│   │   └── firestore.py        # ✅ Pydantic models (User, PDF, Video)
│   ├── pipeline/
│   │   ├── orchestrator.py     # ✅ Main pipeline: PDF → text → script → TTS → render
│   │   └── render.py           # ✅ FFmpeg: gameplay + narration + .ass captions → MP4
│   ├── prompts/
│   │   └── script_rewrite.py   # ✅ Gemma prompt (v3)
│   ├── routes/
│   │   ├── health.py           # ✅ Working
│   │   ├── pdfs.py             # ✅ Upload triggers background pipeline
│   │   ├── feed.py             # TODO
│   │   └── events.py           # TODO
│   └── services/
│       ├── auth.py             # ✅ Dummy user for now
│       ├── firestore.py        # ✅ Firestore CRUD operations
│       ├── ingestion.py        # ✅ PDF text extraction (PyMuPDF)
│       ├── storage.py          # ✅ GCS upload working
│       ├── tts.py              # ✅ ElevenLabs TTS with word timestamps
│       └── vertex.py           # ✅ Gemma 4 script rewriting
├── apps/web/                   # Next.js (empty)
├── packages/shared/            # Shared Pydantic models
├── scripts/
│   ├── create_voice.py         # Create ElevenLabs voice via IVC
│   ├── pipeline_local.py       # Debug pipeline locally
│   ├── seed_gameplay.py        # Seed GCS with gameplay clips
│   └── test_tts.py             # Test TTS service
├── docs/
│   └── data-model.md           # Firestore schema documentation
├── infra/
├── temp/                       # Test files (gitignored)
│   └── deep_vol.pdf            # Test PDF
├── gcp-sa.json                 # GCP service account (gitignored)
└── .env.example
```

---

## 16. Local dev

```bash
# Install deps (from repo root)
uv sync

# Run API server
uv run uvicorn smartscroll.main:app --reload --port 8000

# Test PDF upload (triggers background processing)
curl -X POST http://localhost:8000/api/pdfs/upload -F "file=@temp/deep_vol.pdf"

# Check processing status
curl http://localhost:8000/api/pdfs/{pdf_id}

# List PDFs
curl http://localhost:8000/api/pdfs
```

### Local pipeline testing (no server required)

```bash
# Run full pipeline on a local PDF (outputs to ./output/)
uv run python scripts/pipeline_local.py path/to/paper.pdf

# Specify custom output directory
uv run python scripts/pipeline_local.py path/to/paper.pdf -o ./my_output

# Skip TTS (test text extraction + script generation only)
uv run python scripts/pipeline_local.py path/to/paper.pdf --skip-tts
```

Output files saved to `./output/`:
- `extracted_text.txt` — Raw text from PDF
- `script.txt` — Generated TikTok-style script
- `narration.mp3` — TTS audio (if TTS enabled)
- `timings.json` — Word-level timestamps for captions (if TTS enabled)

---

## 17. Firestore setup

**Database ID:** `smartscroll` (not the default)

**Location:** `us-central1`

**Mode:** Native mode (not Datastore, not MongoDB compatibility)

**Security rules:** Open (for hackathon — API server uses service account which bypasses rules)

**Collections:**
- `users/{uid}` — User profiles
- `users/{uid}/pdfs/{pdfId}` — PDF metadata and status
- `videos/{videoId}` — One video per PDF (top-level for fast feed queries)

See `docs/data-model.md` for full schema.

**Create database (if needed):**
```bash
gcloud firestore databases create --location=us-central1 --database=smartscroll
```

---

## 18. Vertex AI setup

**Service file:** `apps/api/smartscroll/services/vertex.py`

### Gemma 4 MaaS (default)

Uses `google/gemma-4-26b-a4b-it-maas` via the global endpoint. This is the default and recommended approach.

1. Enable Vertex AI API:
```bash
gcloud services enable aiplatform.googleapis.com
```

2. Set env vars in `.env`:
```
GCP_PROJECT_ID=your-project-id
VERTEX_GEMMA_ENDPOINT=               # leave empty for default MaaS model
VERTEX_GEMMA_LOCATION=us-central1
```

3. Test:
```bash
uv run python scripts/pipeline_local.py temp/deep_vol.pdf --skip-tts
```

### Alternative: Deployed endpoint

For dedicated capacity, deploy Gemma 4 from Model Garden to your own endpoint:

1. Go to [Vertex AI Model Garden](https://console.cloud.google.com/vertex-ai/model-garden)
2. Find Gemma 4 → Deploy to endpoint
3. Copy the endpoint ID (numeric)
4. Set in `.env`:
```
VERTEX_GEMMA_ENDPOINT=1234567890123456789
```

**Usage in code:**
```python
from smartscroll.services.vertex import rewrite_pdf_to_script

script, version = await rewrite_pdf_to_script(
    pdf_text="Your full PDF text here...",
    pdf_id="abc123",
)
```

---

## 19. ElevenLabs setup

**Service file:** `apps/api/smartscroll/services/tts.py`

### Voice setup

1. Create a custom voice using Instant Voice Cloning:
```bash
uv run python scripts/create_voice.py temp/narrator.mp3 --name "SmartScroll Narrator"
```

2. Copy the voice ID to `.env`:
```
ELEVENLABS_VOICE_ID=your_voice_id_here
```

3. If the voice requires verification, approve it at [ElevenLabs Voice Lab](https://elevenlabs.io/app/voice-lab).

### API usage

The TTS service uses the `/v1/text-to-speech/{voice_id}/with-timestamps` endpoint, which returns both audio and word-level timing in a single call (no Whisper needed).

```python
from smartscroll.services.tts import generate_speech_with_timestamps, TTSResult

result: TTSResult = await generate_speech_with_timestamps(
    text="Your script text here...",
    # voice_id defaults to ELEVENLABS_VOICE_ID from env
)

# result.audio: bytes (MP3)
# result.word_timings: list[WordTiming(word, start_time, end_time)]
# result.duration_ms: int
```

### Test

```bash
uv run python scripts/test_tts.py
```

Output saved to `temp/test_tts_output.mp3`.

---

## 20. Video rendering setup

**Service file:** `apps/api/smartscroll/pipeline/render.py`

Requires `ffmpeg` installed on the host machine. On Cloud Run, install via the Dockerfile (`apt-get install ffmpeg`).

### Gameplay clip seeding (one-time)

Clips live in `gs://smartscroll-gameplay/`. Seed them once before the first render:

```bash
# Create bucket if it doesn't exist yet
python -c "
from smartscroll.config import get_settings
from google.cloud import storage
s = get_settings()
client = storage.Client()
client.bucket(s.gcs_bucket_gameplay).create(location=s.gcp_region)
"

# Download 4 clips at 1080p and upload to GCS (~10 min)
uv run python scripts/seed_gameplay.py
```

Current clips (hardcoded in `seed_gameplay.py`):
| File | Source |
|------|--------|
| `subway_surfers_1.mp4` | Subway Surfers gameplay (portrait, 9:16) |
| `minecraft_parkour_1.mp4` | Minecraft parkour |
| `minecraft_parkour_2.mp4` | Minecraft parkour |
| `minecraft_parkour_3.mp4` | Minecraft parkour |

The seed script skips clips already present in GCS. To force a re-download (e.g. to upgrade quality), delete the blobs first:
```bash
gcloud storage rm "gs://smartscroll-gameplay/*"
uv run python scripts/seed_gameplay.py
```

### Caption style

Controlled by constants at the top of `render.py`:

| Constant | Value | Effect |
|----------|-------|--------|
| `WORDS_PER_CAPTION` | `5` | Words shown per subtitle cue |
| `OUTPUT_WIDTH` | `1080` | Output pixel width |
| `OUTPUT_HEIGHT` | `1920` | Output pixel height (9:16 portrait) |

The `.ass` style is: Arial 70pt, bold, white with 5px black outline, **alignment 5** (center of screen). To move captions, change the alignment field in `build_ass_captions`: `2` = bottom-center, `5` = mid-center, `8` = top-center.

### Clip selection

`md5(pdf_id) % len(clips)` — same PDF always gets the same gameplay clip. Deterministic but feels random across different PDFs.

### Test render (no full pipeline needed)

If you already have `output/narration.mp3` and `output/timings.json` from `pipeline_local.py`:

```python
import asyncio, json
from pathlib import Path
from smartscroll.pipeline.render import render_video
from smartscroll.services.tts import WordTiming

narration = Path("output/narration.mp3").read_bytes()
timings_raw = json.loads(Path("output/timings.json").read_text())
word_timings = [WordTiming(word=w["word"], start_time=w["start"], end_time=w["end"]) for w in timings_raw]
duration_ms = int(timings_raw[-1]["end"] * 1000)

gcs_uri = asyncio.run(render_video(
    uid="user_demo_123",
    pdf_id="local_test",
    narration_audio=narration,
    word_timings=word_timings,
    duration_ms=duration_ms,
))
print(gcs_uri)
```

Output lands in `gs://smartscroll-rendered/user_demo_123/local_test/video.mp4`.
