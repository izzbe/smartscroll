# SmartScroll

TikTok-style infinite scroll where every video is an AI-narrated summary of a PDF you uploaded, played over Subway Surfers / Minecraft parkour gameplay with burned-in captions.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| pnpm | latest | `npm install -g pnpm` |
| ffmpeg | any | `sudo apt install ffmpeg` / `brew install ffmpeg` |

You also need:
- A **GCP project** with Vertex AI and Firestore enabled, and a service account key (`gcp-sa.json`)
- An **ElevenLabs** account with an API key and a voice ID
- GCS buckets: `smartscroll_pdfs`, `smartscroll-gameplay`, `smartscroll-rendered`

---

## 1. Environment setup

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Required values:

```bash
# GCP
GCP_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=./gcp-sa.json   # path to your service account JSON

# Vertex AI (Gemma 4)
VERTEX_GEMMA_ENDPOINT=                          # leave empty for default MaaS endpoint
VERTEX_GEMMA_LOCATION=us-central1

# Firebase Admin — base64-encoded service account JSON
FIREBASE_ADMIN_CREDENTIALS_JSON=               # base64 of your Firebase service account

# ElevenLabs
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=your-voice-id
```

Place your GCP service account file at `./gcp-sa.json` (or update `GOOGLE_APPLICATION_CREDENTIALS`).

---

## 2. One-time: seed gameplay clips

Before any video can be rendered, the gameplay bucket needs clips. Run this once:

```bash
uv sync
uv run python scripts/seed_gameplay.py
```

This downloads ~4 clips (Subway Surfers, Minecraft parkour) into `gs://smartscroll-gameplay/`. Takes ~10 minutes. Safe to re-run — skips clips already present.

---

## 3. Run the backend

From the repo root:

```bash
uv sync
uv run uvicorn smartscroll.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Check `http://localhost:8000/health` to confirm.

---

## 4. Run the frontend

```bash
cd apps/web
pnpm install
pnpm dev
```

The app is now at `http://localhost:5173`. The Vite dev server proxies all `/api` requests to the backend at port 8000.

---

## 5. Using the app

1. Open `http://localhost:5173`
2. On the **Upload** tab, drop in a PDF (lecture notes, a paper, a textbook chapter)
3. Click **Generate Smart Feed** — the backend extracts text, rewrites it into a TikTok script with Gemma 4, generates audio with ElevenLabs, and renders an MP4 with FFmpeg. This takes 1–3 minutes.
4. The app switches to the **Smart Feed** tab automatically once the video is ready
5. Swipe up/down to scroll through videos
6. Tap the chat bubble to **Ask Gemma** questions about the PDF content

---

## Local pipeline testing (no server needed)

Run the full PDF → MP4 pipeline directly from the command line:

```bash
# Full pipeline
uv run python scripts/pipeline_local.py path/to/paper.pdf

# Skip TTS (text extraction + script only, much faster)
uv run python scripts/pipeline_local.py path/to/paper.pdf --skip-tts

# Custom output directory
uv run python scripts/pipeline_local.py path/to/paper.pdf -o ./my_output
```

Output lands in `./output/`:
- `extracted_text.txt` — raw text from the PDF
- `script.txt` — generated TikTok-style script
- `narration.mp3` — TTS audio (if TTS enabled)
- `timings.json` — word-level timestamps for captions

---

## Project structure

```
smartscroll/
├── apps/
│   ├── web/          # React + Vite frontend (port 5173)
│   └── api/          # FastAPI backend (port 8000)
├── packages/shared/  # Shared Pydantic models
├── scripts/          # One-off utilities (seed, pipeline test, voice creation)
├── infra/            # Dockerfiles, Terraform (optional)
├── .env.example      # Copy to .env and fill in
└── CLAUDE.md         # Full architecture and dev guide
```

---

## API reference (quick)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/pdfs/upload` | Upload a PDF, start background processing |
| GET | `/api/pdfs/{pdf_id}` | Check processing status (`uploading` → `processing` → `ready`) |
| GET | `/api/feed` | Get paginated video feed (recency-scored) |
| POST | `/api/chat/{pdf_id}` | Ask Gemma a question about a PDF's content |

---

## Linting & formatting

```bash
# Python
ruff check .
ruff format .

# Fix automatically
ruff check --fix .
```
