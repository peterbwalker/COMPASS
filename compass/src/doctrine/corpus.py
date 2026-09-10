"""
Doctrine corpus loading and chunking.

Loads .pdf and .txt files from a directory (default: doctrine/ at the
repo root) and splits them into overlapping word-count chunks for BM25
indexing. This is intentionally simple -- no embeddings, no external API
-- so it has zero additional cost or credentials beyond what's already
in requirements.txt.

Populate the doctrine/ folder yourself with PDFs downloaded from
authoritative sources (jcs.mil, armypubs.army.mil, doctrine.af.mil, etc.
-- see docs/doctrine-references.md for a starting list). This module
doesn't fetch anything on your behalf, so you control exactly which
version of which document is in the corpus.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from pypdf import PdfReader


@dataclass
class DoctrineChunk:
    source: str  # filename the chunk came from
    chunk_id: int  # index of this chunk within its source document
    text: str


def _extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")


def chunk_text(text: str, chunk_size: int = 220, overlap: int = 40) -> List[str]:
    """
    Split text into overlapping chunks by word count. Word-count
    chunking (rather than character count) keeps chunks a fairly
    consistent semantic size regardless of formatting quirks in
    PDF-extracted text (extra whitespace, line breaks mid-sentence).

    Args:
        text: raw extracted text.
        chunk_size: target words per chunk.
        overlap: words shared between consecutive chunks, so a relevant
            passage that straddles a chunk boundary isn't lost entirely.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(words):
        chunk_words = words[start : start + chunk_size]
        chunks.append(" ".join(chunk_words))
        start += step
    return chunks


def load_corpus(doctrine_dir: str = "doctrine") -> List[DoctrineChunk]:
    """
    Load and chunk every .pdf/.txt file in doctrine_dir. Returns an
    empty list (not an error) if the directory doesn't exist or has no
    supported files -- callers should treat "no doctrine corpus yet" as
    a normal, expected state, not a failure.
    """
    dir_path = Path(doctrine_dir)
    if not dir_path.is_dir():
        return []

    chunks: List[DoctrineChunk] = []
    for path in sorted(dir_path.iterdir()):
        if path.suffix.lower() not in (".pdf", ".txt"):
            continue
        try:
            text = _extract_text(path)
        except Exception:
            # A single malformed/unreadable file shouldn't take down the
            # whole corpus load -- skip it and continue with the rest.
            continue

        for i, chunk in enumerate(chunk_text(text)):
            chunks.append(DoctrineChunk(source=path.name, chunk_id=i, text=chunk))

    return chunks
