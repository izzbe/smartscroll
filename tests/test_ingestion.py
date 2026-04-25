"""
tests/test_ingestion.py — Unit tests for smartscroll.ingestion.

All tests use synthetic PDFs built in memory with PyMuPDF so there are
no external file dependencies.  A few helpers at the top create reusable
PDF bytes that fixtures pass into the functions under test.
"""

from __future__ import annotations

import io

import fitz  # PyMuPDF
import pytest

from smartscroll.ingestion import (
    SmartChunk,
    chunk_pdf_semantically,
    create_semantic_chunks,
    describe_image,
    extract_pdf_content,
    split_into_paragraphs,
)

# ---------------------------------------------------------------------------
# Helpers — build synthetic PDFs as bytes in memory
# ---------------------------------------------------------------------------

# A paragraph long enough to pass the MIN_PARAGRAPH_CHARS filter (>= 40 chars).
SHORT_PARA = "The quick brown fox jumps over the lazy dog. " * 3
LONG_PARA = "Artificial intelligence is transforming how we process documents. " * 6


def _make_pdf(pages_text: list[str], include_image: bool = False) -> bytes:
    """
    Return a PDF as raw bytes.

    pages_text   — one string per page; each string is written as plain text.
    include_image — if True, a small synthetic image is embedded on page 1.
    """
    doc = fitz.open()

    for i, text in enumerate(pages_text):
        page = doc.new_page()
        page.insert_text((72, 72), text)

        if include_image and i == 0:
            # Create a minimal 10x10 red PNG in memory and embed it.
            import struct, zlib

            def _png_bytes() -> bytes:
                # Minimal valid 10x10 red PNG, hand-crafted.
                width, height = 10, 10
                raw_row = b"\x00" + b"\xff\x00\x00" * width  # filter byte + RGB pixels
                raw_data = raw_row * height
                compressed = zlib.compress(raw_data)

                def chunk(name: bytes, data: bytes) -> bytes:
                    c = name + data
                    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

                ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
                return (
                    b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", ihdr_data)
                    + chunk(b"IDAT", compressed)
                    + chunk(b"IEND", b"")
                )

            png = _png_bytes()
            rect = fitz.Rect(200, 200, 210, 210)
            page.insert_image(rect, stream=png)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _save_tmp_pdf(tmp_path, pages_text: list[str], include_image: bool = False) -> str:
    """Write a synthetic PDF to a temp file and return its path string."""
    pdf_bytes = _make_pdf(pages_text, include_image=include_image)
    path = tmp_path / "test.pdf"
    path.write_bytes(pdf_bytes)
    return str(path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def single_page_pdf(tmp_path) -> str:
    """One page with two substantial paragraphs."""
    text = f"{LONG_PARA}\n\n{SHORT_PARA}"
    return _save_tmp_pdf(tmp_path, [text])


@pytest.fixture()
def multi_page_pdf(tmp_path) -> str:
    """Three pages, each with distinct content."""
    return _save_tmp_pdf(
        tmp_path,
        [
            f"Page one discusses machine learning.\n\n{LONG_PARA}",
            f"Page two is about cooking recipes.\n\n{SHORT_PARA}",
            f"Page three covers ancient history.\n\n{SHORT_PARA}",
        ],
    )


@pytest.fixture()
def image_pdf(tmp_path) -> str:
    """One page with text and one embedded image."""
    return _save_tmp_pdf(tmp_path, [LONG_PARA], include_image=True)


@pytest.fixture()
def empty_text_pdf(tmp_path) -> str:
    """A valid PDF whose page contains only whitespace (no real text)."""
    return _save_tmp_pdf(tmp_path, ["   \n  \n   "])


# ---------------------------------------------------------------------------
# describe_image
# ---------------------------------------------------------------------------


class TestDescribeImage:
    def test_returns_string(self):
        result = describe_image(b"fake image bytes")
        assert isinstance(result, str)

    def test_not_empty(self):
        result = describe_image(b"fake image bytes")
        assert len(result) > 0

    def test_works_with_empty_bytes(self):
        # Should not raise even when given no bytes.
        result = describe_image(b"")
        assert isinstance(result, str)

    def test_placeholder_message(self):
        # The placeholder text makes it easy to know the stub is still wired.
        result = describe_image(b"anything")
        assert "image" in result.lower()


# ---------------------------------------------------------------------------
# extract_pdf_content
# ---------------------------------------------------------------------------


class TestExtractPdfContent:
    def test_returns_list(self, single_page_pdf):
        pages = extract_pdf_content(single_page_pdf)
        assert isinstance(pages, list)

    def test_page_count_matches(self, multi_page_pdf):
        pages = extract_pdf_content(multi_page_pdf)
        assert len(pages) == 3

    def test_page_numbers_are_one_indexed(self, multi_page_pdf):
        pages = extract_pdf_content(multi_page_pdf)
        assert pages[0]["page_number"] == 1
        assert pages[2]["page_number"] == 3

    def test_text_is_extracted(self, single_page_pdf):
        pages = extract_pdf_content(single_page_pdf)
        combined = " ".join(p["text"] for p in pages)
        assert "fox" in combined  # from SHORT_PARA

    def test_images_key_exists(self, single_page_pdf):
        pages = extract_pdf_content(single_page_pdf)
        for page in pages:
            assert "images" in page
            assert isinstance(page["images"], list)

    def test_image_detected_on_image_page(self, image_pdf):
        pages = extract_pdf_content(image_pdf)
        # The embedded image should trigger describe_image on page 1.
        assert len(pages[0]["images"]) >= 1

    def test_no_images_on_plain_page(self, single_page_pdf):
        pages = extract_pdf_content(single_page_pdf)
        assert pages[0]["images"] == []

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            extract_pdf_content("/tmp/this_file_does_not_exist_xyz.pdf")

    def test_empty_path_raises_value_error(self):
        with pytest.raises(ValueError):
            extract_pdf_content("")


# ---------------------------------------------------------------------------
# split_into_paragraphs
# ---------------------------------------------------------------------------


class TestSplitIntoParagraphs:
    def test_returns_list_of_dicts(self, single_page_pdf):
        pages = extract_pdf_content(single_page_pdf)
        paras = split_into_paragraphs(pages)
        assert isinstance(paras, list)
        assert all(isinstance(p, dict) for p in paras)

    def test_each_paragraph_has_required_keys(self, single_page_pdf):
        pages = extract_pdf_content(single_page_pdf)
        paras = split_into_paragraphs(pages)
        for para in paras:
            assert "page_number" in para
            assert "text" in para
            assert "images" in para

    def test_tiny_fragments_are_dropped(self):
        # Build a fake pages list with a mix of real and tiny content.
        fake_pages = [
            {
                "page_number": 1,
                "text": f"hi\n\n{LONG_PARA}",  # "hi" is too short
                "images": [],
            }
        ]
        paras = split_into_paragraphs(fake_pages)
        texts = [p["text"] for p in paras]
        assert not any(t == "hi" for t in texts)

    def test_whitespace_is_normalised(self):
        fake_pages = [
            {
                "page_number": 1,
                "text": "  word1   word2   word3  " * 5,
                "images": [],
            }
        ]
        paras = split_into_paragraphs(fake_pages)
        for para in paras:
            # No leading/trailing whitespace, no double spaces.
            assert para["text"] == para["text"].strip()
            assert "  " not in para["text"]

    def test_images_only_on_first_paragraph_of_page(self):
        fake_pages = [
            {
                "page_number": 1,
                "text": f"{LONG_PARA}\n\n{SHORT_PARA}",
                "images": ["some image description"],
            }
        ]
        paras = split_into_paragraphs(fake_pages)
        # Expect at least two paragraphs
        assert len(paras) >= 2
        # Only the first paragraph should carry the image.
        assert len(paras[0]["images"]) == 1
        assert paras[1]["images"] == []

    def test_empty_pages_returns_empty_list(self):
        paras = split_into_paragraphs([])
        assert paras == []

    def test_page_numbers_are_preserved(self, multi_page_pdf):
        pages = extract_pdf_content(multi_page_pdf)
        paras = split_into_paragraphs(pages)
        page_numbers = {p["page_number"] for p in paras}
        # We should see at least pages 1, 2, and 3.
        assert {1, 2, 3}.issubset(page_numbers)


# ---------------------------------------------------------------------------
# create_semantic_chunks
# ---------------------------------------------------------------------------


def _make_paragraphs(texts: list[str], page_number: int = 1) -> list[dict]:
    """Build a minimal paragraph list for feeding into create_semantic_chunks."""
    return [{"page_number": page_number, "text": t, "images": []} for t in texts]


class TestCreateSemanticChunks:
    def test_returns_list_of_smart_chunks(self):
        paras = _make_paragraphs([LONG_PARA, SHORT_PARA])
        chunks = create_semantic_chunks(paras, source_file="test.pdf")
        assert isinstance(chunks, list)
        assert all(isinstance(c, SmartChunk) for c in chunks)

    def test_chunk_ids_are_sequential(self):
        paras = _make_paragraphs([LONG_PARA] * 6)
        chunks = create_semantic_chunks(
            paras, source_file="test.pdf", similarity_threshold=1.1  # force splits
        )
        ids = [c.chunk_id for c in chunks]
        assert ids == list(range(len(chunks)))

    def test_source_file_is_stored(self):
        paras = _make_paragraphs([LONG_PARA])
        chunks = create_semantic_chunks(paras, source_file="my_paper.pdf")
        assert all(c.source_file == "my_paper.pdf" for c in chunks)

    def test_no_chunk_exceeds_max_chars(self):
        max_chars = 300
        # Feed many similar paragraphs; without the char limit they'd merge.
        paras = _make_paragraphs([SHORT_PARA] * 10)
        chunks = create_semantic_chunks(
            paras,
            source_file="test.pdf",
            similarity_threshold=0.0,  # always try to merge
            max_chunk_chars=max_chars,
        )
        for chunk in chunks:
            assert len(chunk.text) <= max_chars, (
                f"Chunk {chunk.chunk_id} has {len(chunk.text)} chars, limit is {max_chars}"
            )

    def test_high_threshold_produces_more_chunks(self):
        paras = _make_paragraphs([LONG_PARA] * 5)
        loose = create_semantic_chunks(paras, source_file="t.pdf", similarity_threshold=0.0)
        strict = create_semantic_chunks(paras, source_file="t.pdf", similarity_threshold=1.1)
        assert len(strict) >= len(loose)

    def test_single_paragraph_becomes_one_chunk(self):
        paras = _make_paragraphs([LONG_PARA])
        chunks = create_semantic_chunks(paras, source_file="t.pdf")
        assert len(chunks) == 1
        assert chunks[0].text == LONG_PARA

    def test_empty_input_returns_empty_list(self):
        chunks = create_semantic_chunks([], source_file="t.pdf")
        assert chunks == []

    def test_page_range_is_correct(self):
        paras = [
            {"page_number": 1, "text": LONG_PARA, "images": []},
            {"page_number": 2, "text": LONG_PARA, "images": []},
        ]
        # Force merge by using a very low threshold and large char limit.
        chunks = create_semantic_chunks(
            paras, source_file="t.pdf", similarity_threshold=0.0, max_chunk_chars=99999
        )
        merged = chunks[0]
        assert merged.page_start == 1
        assert merged.page_end == 2

    def test_image_descriptions_are_carried_through(self):
        paras = [
            {"page_number": 1, "text": LONG_PARA, "images": ["a diagram of a network"]},
            {"page_number": 1, "text": SHORT_PARA, "images": []},
        ]
        chunks = create_semantic_chunks(
            paras, source_file="t.pdf", similarity_threshold=0.0, max_chunk_chars=99999
        )
        all_images = [img for c in chunks for img in c.image_descriptions]
        assert "a diagram of a network" in all_images

    def test_chunk_text_is_non_empty(self):
        paras = _make_paragraphs([LONG_PARA, SHORT_PARA])
        chunks = create_semantic_chunks(paras, source_file="t.pdf")
        for chunk in chunks:
            assert chunk.text.strip() != ""


# ---------------------------------------------------------------------------
# chunk_pdf_semantically  (full pipeline)
# ---------------------------------------------------------------------------


class TestChunkPdfSemantically:
    def test_returns_non_empty_list(self, single_page_pdf):
        chunks = chunk_pdf_semantically(single_page_pdf)
        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_all_items_are_smart_chunks(self, single_page_pdf):
        chunks = chunk_pdf_semantically(single_page_pdf)
        assert all(isinstance(c, SmartChunk) for c in chunks)

    def test_multi_page_pdf_covers_all_pages(self, multi_page_pdf):
        chunks = chunk_pdf_semantically(multi_page_pdf)
        all_pages = {p for c in chunks for p in range(c.page_start, c.page_end + 1)}
        assert 1 in all_pages
        assert 3 in all_pages

    def test_image_pdf_has_image_descriptions(self, image_pdf):
        chunks = chunk_pdf_semantically(image_pdf)
        all_images = [img for c in chunks for img in c.image_descriptions]
        assert len(all_images) >= 1

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            chunk_pdf_semantically("/tmp/does_not_exist_abc123.pdf")

    def test_empty_text_pdf_raises_runtime_error(self, empty_text_pdf):
        with pytest.raises(RuntimeError):
            chunk_pdf_semantically(empty_text_pdf)

    def test_chunk_ids_start_at_zero(self, single_page_pdf):
        chunks = chunk_pdf_semantically(single_page_pdf)
        assert chunks[0].chunk_id == 0

    def test_source_file_matches_input(self, single_page_pdf):
        chunks = chunk_pdf_semantically(single_page_pdf)
        assert all(c.source_file == single_page_pdf for c in chunks)
