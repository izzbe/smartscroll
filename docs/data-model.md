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
| `errorMessage` | `string?` | Error details if `status == "failed"` |

---

## `videos/{videoId}`
Video document — one video per PDF. **This is the primary read path for the feed.**

| Field | Type | Description |
|-------|------|-------------|
| `uid` | `string` | Owner user ID |
| `pdfId` | `string` | Source PDF ID |
| `pdfFilename` | `string` | Original PDF filename (for display) |
| `videoGcsPath` | `string` | GCS path to MP4 |
| `durationMs` | `int` | Video duration |
| `script` | `string` | Rewritten TikTok-style script |
| `scriptPromptVersion` | `int` | Version of prompt used (for A/B) |
| `wordCount` | `int` | Words in the script |
| `createdAt` | `timestamp` | Video creation time |
| `viewCount` | `int` | Number of views |
| `totalWatchMs` | `int` | Total watch time across all views |

---

## Relationships

```
users/{uid}
  └── pdfs/{pdfId}           # 1:N - user has many PDFs

videos/{videoId}             # 1:1 with PDF, denormalized for fast feed reads
```

---

## Design Notes

1. **One PDF = One Video** — no chunking, the entire PDF is processed into a single video
2. **Feed reads from `videos/` only** — no joins at request time
3. **Write denormalized** — when a video finishes rendering, write to `videos/{videoId}`
4. **Status polling** — frontend uses Firestore realtime listener on `pdfs/{pdfId}` to track processing status
5. **Analytics** — `viewCount` and `totalWatchMs` updated via `/api/events` endpoint
