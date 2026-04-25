# SmartScroll

> **One-liner:** TikTok-style infinite scroll where every video is a 60-second AI-narrated summary of a PDF the user uploaded, played over Subway Surfers / Minecraft parkour gameplay with burned-in captions. Productive brainrot.

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
- **Object storage**: GCS — buckets `smartscroll-pdfs`, `smartscroll-gameplay`, `smartscroll-rendered`.
- **Job runner**: FastAPI `BackgroundTasks` for the hackathon. Cloud Tasks + a separate Cloud Run worker is the upgrade path; do NOT build that now.
- **Transcription/timestamps**: `faster-whisper` (large-v3) running in the API container. Word-level timestamps required.
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
│   ├── seed_gameplay.py    # One-time: download N gameplay clips into GCS
│   └── pipeline_local.py   # Run the full ingest pipeline on a local PDF for debugging
├── .env.example
├── CLAUDE.md           # this file
└── README.md           # human-facing setup
```

Always put new code in the right app. Shared types go in `packages/shared` — never copy a Pydantic model into the frontend; generate it.

---

## 3. The pipeline (the heart of the app)

Ingestion runs when a user uploads a PDF. End-to-end, per chunk:

```
PDF upload
  └─> [1] Extract text (PyMuPDF) + structural hints (headings, page breaks)
  └─> [2] Semantic chunking — see §3.1. Target ~150 spoken words per chunk (~60s @ 150wpm).
  └─> [3] For each chunk, in parallel:
        ├─ [3a] Gemma 4 → rewrite chunk into a TikTok-voice script (see §3.2 for prompt rules)
        ├─ [3b] ElevenLabs → narration MP3 from the script
        ├─ [3c] faster-whisper on the MP3 → word-level timestamps
        ├─ [3d] Pick a random gameplay clip from GCS, trim to audio length
        ├─ [3e] Generate .ass subtitle file from word timestamps (TikTok-style: 1-3 words at a time, bouncy)
        └─ [3f] FFmpeg: mux gameplay video + narration audio + burned-in captions → final MP4 to GCS
  └─> [4] Write chunk + video metadata to Firestore. Mark PDF status = ready.
```

Each chunk is independent. Process them concurrently with `asyncio.gather` — do not serialize them.

### 3.1 Semantic chunking

Default: split on headings/sections from PyMuPDF's TOC + paragraph boundaries. Greedy-pack paragraphs until ~150 words.

**LLM-assisted edge cases** (use Gemma 4 only when needed, it's not free):
- A "section" is >300 words → ask Gemma to split it into 2-3 self-contained sub-points.
- A "section" is <60 words → merge with neighbor.
- Equations, code blocks, or figures detected → ask Gemma whether to skip, paraphrase, or describe.

Chunks must be **self-contained**. The viewer drops in mid-feed — no "as we discussed earlier."

### 3.2 Script rewriting (the Gemma prompt)

The script is the make-or-break of the app. Hard rules baked into the system prompt:

- **140-160 spoken words.** Count words, not tokens.
- **Hook in the first 8 words.** "Here's why X is wild:" / "Most people get Y completely wrong:" / "There's a study that…"
- **Conversational, second-person, present tense.** No "the author argues." Yes "so basically what they found is…"
- **No filler intros** ("In this video we'll explore…"). Drop straight into the content.
- **End on a payoff or a cliffhanger**, never a summary.
- **Plain text only.** No markdown, no headers, no bullets — this gets fed to TTS.

Keep the prompt in `apps/api/smartscroll/prompts/script_rewrite.py` as a single source of truth. Version it (`SCRIPT_PROMPT_V = 3`) and log the version with each generated chunk so we can A/B.

### 3.3 What the LLM is NOT for

- Don't use Gemma to pick gameplay clips. Random with seed = chunk_id is fine.
- Don't use Gemma to score/rank the feed. Use the deterministic algorithm in §5.
- Don't use Gemma for OCR. PyMuPDF handles text extraction; if the PDF is scanned, fall back to Vertex Document AI, not Gemma.

---

## 4. Data model (Firestore)

```
users/{uid}
  email, displayName, createdAt

users/{uid}/pdfs/{pdfId}
  filename, gcsPath, status: "uploading"|"processing"|"ready"|"failed",
  uploadedAt, chunkCount, errorMessage?

users/{uid}/pdfs/{pdfId}/chunks/{chunkId}
  index, sourceText, script, scriptPromptVersion,
  narrationGcsPath, videoGcsPath, durationMs,
  wordCount, createdAt

videos/{videoId}     # denormalized for fast feed reads
  uid, pdfId, chunkId, videoGcsPath, durationMs,
  createdAt, viewCount, totalWatchMs
```

**Rule:** the feed endpoint reads from `videos/` only. Never join across `users/{uid}/pdfs/.../chunks` at request time — that's a fan-out latency disaster. Denormalize on write.

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
GCS_BUCKET_PDFS=smartscroll-pdfs
GCS_BUCKET_GAMEPLAY=smartscroll-gameplay
GCS_BUCKET_RENDERED=smartscroll-rendered
GOOGLE_APPLICATION_CREDENTIALS=./gcp-sa.json   # local only

# Vertex AI / Gemma 4
VERTEX_GEMMA_ENDPOINT=         # Model Garden endpoint for gemma-4-26b-moe-it
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
# Backend
cd apps/api
uv sync
uv run uvicorn smartscroll.main:app --reload --port 8000

# Frontend
cd apps/web
pnpm install
pnpm dev   # localhost:3000

# Run the full pipeline on a local PDF without the API
uv run python scripts/pipeline_local.py path/to/paper.pdf
```

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
- ❌ Don't generate captions with Gemma. Use Whisper word timestamps. Gemma hallucinates timing.
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