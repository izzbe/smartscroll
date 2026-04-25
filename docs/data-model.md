# Firestore Object Model

## `users/{uid}`
Top-level user document.

| Field | Type | Description |
|-------|------|-------------|
| `email` | `string` | User's email address |
| `displayName` | `string` | Display name |
| `createdAt` | `timestamp` | Account creation time |

---

## `users/{uid}/pdfs/{pdfId}`
PDF uploaded by a user. Subcollection of user.

| Field | Type | Description |
|-------|------|-------------|
| `filename` | `string` | Original filename (e.g., `deep_vol.pdf`) |
| `gcsPath` | `string` | GCS URI (`gs://smartscroll_pdfs/...`) |
| `status` | `string` | `"uploading"` \| `"processing"` \| `"ready"` \| `"failed"` |
| `uploadedAt` | `timestamp` | Upload time |
| `chunkCount` | `int` | Number of chunks generated (set after processing) |
| `errorMessage` | `string?` | Error details if `status == "failed"` |

---

## `users/{uid}/pdfs/{pdfId}/chunks/{chunkId}`
A single chunk of a PDF. Subcollection of pdf.

| Field | Type | Description |
|-------|------|-------------|
| `index` | `int` | Order in the PDF (0-indexed) |
| `sourceText` | `string` | Raw extracted text from PDF |
| `script` | `string` | Rewritten TikTok-style script |
| `scriptPromptVersion` | `int` | Version of prompt used (for A/B) |
| `narrationGcsPath` | `string` | GCS path to MP3 narration |
| `videoGcsPath` | `string` | GCS path to final MP4 |
| `durationMs` | `int` | Video duration in milliseconds |
| `wordCount` | `int` | Words in the script |
| `createdAt` | `timestamp` | Chunk creation time |

---

## `videos/{videoId}`
Denormalized video document for fast feed reads. **This is the primary read path for the feed.**

| Field | Type | Description |
|-------|------|-------------|
| `uid` | `string` | Owner user ID |
| `pdfId` | `string` | Source PDF ID |
| `chunkId` | `string` | Source chunk ID |
| `pdfFilename` | `string` | Original PDF filename (for display) |
| `chunkIndex` | `int` | Chunk order in PDF |
| `videoGcsPath` | `string` | GCS path to MP4 |
| `durationMs` | `int` | Video duration |
| `createdAt` | `timestamp` | Video creation time |
| `viewCount` | `int` | Number of views |
| `totalWatchMs` | `int` | Total watch time across all views |

---

## Relationships

```
users/{uid}
  └── pdfs/{pdfId}           # 1:N - user has many PDFs
        └── chunks/{chunkId}  # 1:N - PDF has many chunks

videos/{videoId}             # Denormalized, references uid/pdfId/chunkId
```

---

## Design Notes

1. **Feed reads from `videos/` only** — no joins at request time
2. **Write denormalized** — when a chunk finishes rendering, write to both `chunks/{chunkId}` and `videos/{videoId}`
3. **Status polling** — frontend uses Firestore realtime listener on `pdfs/{pdfId}` to track processing status
4. **Analytics** — `viewCount` and `totalWatchMs` updated via `/api/events` endpoint
