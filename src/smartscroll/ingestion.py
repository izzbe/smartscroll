"""
ingestion.py — Semantic PDF chunker for SmartScroll.

Reads a PDF, extracts text and embedded images page by page, groups
paragraphs into semantically-related chunks using sentence embeddings
and cosine similarity, and returns structured SmartChunk objects.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SmartChunk:
    chunk_id: int
    page_start: int
    page_end: int
    text: str
    image_descriptions: list[str]
    source_file: str


# ---------------------------------------------------------------------------
# Image description (placeholder — swap in a vision model here later)
# ---------------------------------------------------------------------------


def describe_image(image_bytes: bytes) -> str:
    """
    Return a human-readable description of an embedded PDF image.

    This is a placeholder. To connect a real vision model, replace the
    body of this function with a call to, e.g.:
        - openai.chat.completions.create(..., model="gpt-4o")
        - google.generativeai.GenerativeModel("gemini-pro-vision")
        - anthropic.messages.create(..., model="claude-opus-4-5")

    The function signature must stay the same so the rest of the code
    doesn't need to change.
    """
    _ = image_bytes  # not used until a real model is wired in
    return "Embedded image detected. Image analysis not yet connected."


# ---------------------------------------------------------------------------
# Step 1 — extract raw text + images, page by page
# ---------------------------------------------------------------------------


def extract_pdf_content(pdf_path: str) -> list[dict]:
    """
    Open the PDF and return one dict per page with keys:
        page_number  int   (1-indexed)
        text         str   raw page text
        images       list  of image-description strings
    """
    if not pdf_path:
        raise ValueError("pdf_path must not be empty.")

    try:
        doc = fitz.open(pdf_path)
    except (FileNotFoundError, fitz.FileNotFoundError):
        # fitz.FileNotFoundError is not a subclass of the builtin, so catch both.
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    except Exception as exc:
        raise RuntimeError(f"Could not open PDF '{pdf_path}': {exc}") from exc

    if doc.page_count == 0:
        raise RuntimeError(f"PDF '{pdf_path}' contains no pages.")

    pages: list[dict] = []

    for page_index in range(doc.page_count):
        page = doc[page_index]
        page_number = page_index + 1  # human-friendly 1-based numbering

        # --- text ---
        raw_text = page.get_text("text")  # plain text, preserves line breaks

        # --- embedded images ---
        image_descriptions: list[str] = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]  # cross-reference index inside the PDF
            try:
                base_image = doc.extract_image(xref)
                img_bytes: bytes = base_image["image"]
                description = describe_image(img_bytes)
                image_descriptions.append(description)
            except Exception:
                # If a single image is unreadable, skip it gracefully.
                image_descriptions.append("Embedded image could not be read.")

        pages.append(
            {
                "page_number": page_number,
                "text": raw_text,
                "images": image_descriptions,
            }
        )

    doc.close()
    return pages


# ---------------------------------------------------------------------------
# Step 2 — clean text and split into paragraph-level units
# ---------------------------------------------------------------------------


def split_into_paragraphs(pages: list[dict]) -> list[dict]:
    """
    Clean the raw text from each page and split it into paragraphs.

    Returns a list of dicts, one per paragraph:
        page_number  int
        text         str   cleaned paragraph text
        images       list  image descriptions from the same page
                          (attached only to the *first* paragraph of the page)
    """
    MIN_PARAGRAPH_CHARS = 40  # ignore fragments shorter than this

    paragraphs: list[dict] = []

    for page in pages:
        raw_text: str = page["text"]
        page_num: int = page["page_number"]
        page_images: list[str] = page["images"]

        # Split on blank lines (two or more newlines) to get paragraphs.
        # Fall back to single-newline splits when the page has dense text
        # with no blank-line separators.
        raw_blocks = [b for b in raw_text.split("\n\n") if b.strip()]
        if len(raw_blocks) <= 1:
            # Try single newlines as paragraph separators
            raw_blocks = [b for b in raw_text.split("\n") if b.strip()]

        first_paragraph_on_page = True

        for block in raw_blocks:
            # Normalise internal whitespace
            cleaned = " ".join(block.split())

            # Skip tiny fragments (page numbers, headers, lone words, etc.)
            if len(cleaned) < MIN_PARAGRAPH_CHARS:
                continue

            # Attach images only to the first paragraph of each page so
            # they don't get duplicated across every paragraph.
            images_for_this_paragraph = page_images if first_paragraph_on_page else []
            first_paragraph_on_page = False

            paragraphs.append(
                {
                    "page_number": page_num,
                    "text": cleaned,
                    "images": images_for_this_paragraph,
                }
            )

    return paragraphs


# ---------------------------------------------------------------------------
# Step 3 — group paragraphs into semantic chunks
# ---------------------------------------------------------------------------

# Load the embedding model once at module level so it is not reloaded on
# every function call.  'all-MiniLM-L6-v2' is small (~80 MB) and fast.
_EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")


def create_semantic_chunks(
    paragraphs: list[dict],
    source_file: str,
    similarity_threshold: float = 0.55,
    max_chunk_chars: int = 1800,
) -> list[SmartChunk]:
    """
    Group paragraphs into semantically cohesive chunks.

    Two adjacent paragraphs are merged into the same chunk when:
      1. Their cosine similarity is >= similarity_threshold, AND
      2. The combined text would not exceed max_chunk_chars.

    Parameters
    ----------
    paragraphs          Output of split_into_paragraphs().
    source_file         Original PDF path — stored in every chunk.
    similarity_threshold
                        0.0–1.0.  Higher → stricter grouping (more, smaller
                        chunks).  Lower → looser grouping (fewer, bigger
                        chunks).  0.55 is a good starting point.
    max_chunk_chars     Hard ceiling on chunk text length.
    """
    if not paragraphs:
        return []

    texts = [p["text"] for p in paragraphs]

    # Encode all paragraphs in one batch (fast; uses GPU if available).
    embeddings = _EMBEDDING_MODEL.encode(texts, convert_to_numpy=True)

    chunks: list[SmartChunk] = []
    chunk_id = 0

    # Accumulator for the current in-progress chunk
    current_texts: list[str] = [texts[0]]
    current_images: list[str] = list(paragraphs[0]["images"])
    current_page_start: int = paragraphs[0]["page_number"]
    current_page_end: int = paragraphs[0]["page_number"]

    for i in range(1, len(paragraphs)):
        prev_embedding = embeddings[i - 1].reshape(1, -1)
        curr_embedding = embeddings[i].reshape(1, -1)
        similarity: float = float(cosine_similarity(prev_embedding, curr_embedding)[0][0])

        would_be_text = " ".join(current_texts) + " " + texts[i]
        fits_in_chunk = len(would_be_text) <= max_chunk_chars
        is_similar = similarity >= similarity_threshold

        if is_similar and fits_in_chunk:
            # Merge this paragraph into the current chunk.
            current_texts.append(texts[i])
            current_images.extend(paragraphs[i]["images"])
            current_page_end = paragraphs[i]["page_number"]
        else:
            # Finalise the current chunk and start a new one.
            chunks.append(
                SmartChunk(
                    chunk_id=chunk_id,
                    page_start=current_page_start,
                    page_end=current_page_end,
                    text=" ".join(current_texts),
                    image_descriptions=current_images,
                    source_file=source_file,
                )
            )
            chunk_id += 1
            current_texts = [texts[i]]
            current_images = list(paragraphs[i]["images"])
            current_page_start = paragraphs[i]["page_number"]
            current_page_end = paragraphs[i]["page_number"]

    # Don't forget the last in-progress chunk.
    chunks.append(
        SmartChunk(
            chunk_id=chunk_id,
            page_start=current_page_start,
            page_end=current_page_end,
            text=" ".join(current_texts),
            image_descriptions=current_images,
            source_file=source_file,
        )
    )

    return chunks


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def chunk_pdf_semantically(pdf_path: str) -> list[SmartChunk]:
    """
    Full pipeline: PDF → semantic SmartChunk list.

    Usage
    -----
    chunks = chunk_pdf_semantically("my_paper.pdf")
    for chunk in chunks:
        print(chunk.text[:200])
    """
    pages = extract_pdf_content(pdf_path)
    paragraphs = split_into_paragraphs(pages)

    if not paragraphs:
        raise RuntimeError(f"No readable text found in '{pdf_path}'.")

    return create_semantic_chunks(paragraphs, source_file=pdf_path)


# ---------------------------------------------------------------------------
# CLI / quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/smartscroll/ingestion.py path/to/sample.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"\nProcessing: {pdf_path}\n{'=' * 60}")

    try:
        chunks = chunk_pdf_semantically(pdf_path)
    except (FileNotFoundError, RuntimeError) as err:
        print(f"Error: {err}")
        sys.exit(1)

    print(f"Total chunks: {len(chunks)}\n")

    for chunk in chunks:
        print(f"--- Chunk {chunk.chunk_id} | Pages {chunk.page_start}–{chunk.page_end} ---")
        print(chunk.text[:500])
        if chunk.image_descriptions:
            print("\n[Images]")
            for desc in chunk.image_descriptions:
                print(f"  • {desc}")
        print()
