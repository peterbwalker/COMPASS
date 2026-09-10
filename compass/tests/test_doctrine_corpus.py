from src.doctrine.corpus import chunk_text, load_corpus


def test_chunk_text_respects_overlap():
    words = [f"word{i}" for i in range(50)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=20, overlap=5)

    assert len(chunks) > 1
    first_chunk_words = chunks[0].split()
    second_chunk_words = chunks[1].split()
    # Last `overlap` words of chunk 1 should match first `overlap` words of chunk 2
    assert first_chunk_words[-5:] == second_chunk_words[:5]


def test_chunk_text_empty_input():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_load_corpus_missing_directory_returns_empty():
    assert load_corpus("this_directory_does_not_exist") == []


def test_load_corpus_reads_txt_files(tmp_path):
    (tmp_path / "sample_doctrine.txt").write_text(
        "This is a test fixture standing in for a doctrine excerpt. " * 30
    )
    chunks = load_corpus(str(tmp_path))
    assert len(chunks) > 0
    assert all(c.source == "sample_doctrine.txt" for c in chunks)


def test_load_corpus_skips_unsupported_file_types(tmp_path):
    (tmp_path / "notes.md").write_text("irrelevant")
    (tmp_path / "doc.txt").write_text("relevant text " * 30)

    chunks = load_corpus(str(tmp_path))
    assert all(c.source == "doc.txt" for c in chunks)


def test_load_corpus_reads_pdf_files(tmp_path):
    """
    Generates a minimal real PDF at test-time (via reportlab) rather than
    committing a static binary fixture or depending on pdflatex being
    installed wherever these tests run -- keeps the test self-contained.
    """
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "sample_doctrine.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(
        100, 750,
        "This is a test fixture PDF standing in for a doctrine document."
    )
    c.save()

    chunks = load_corpus(str(tmp_path))
    assert len(chunks) > 0
    assert chunks[0].source == "sample_doctrine.pdf"
    assert "test fixture" in chunks[0].text
