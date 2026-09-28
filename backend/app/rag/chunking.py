"""Split documents into overlapping, paragraph-aware chunks for embedding."""

import io
import re
from pathlib import PurePath

from pypdf import PdfReader

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml", ".html", ".xml",
    ".py", ".ts", ".js", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".sql", ".sh", ".toml", ".ini",
}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf"}


class UnsupportedFileError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    ext = PurePath(filename).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(f"[Page {i + 1}]\n{text}" for i, text in enumerate(pages) if text.strip())
    if ext in TEXT_EXTENSIONS:
        return data.decode("utf-8", errors="replace")
    raise UnsupportedFileError(
        f"Unsupported file type '{ext or filename}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """Greedily pack paragraphs into chunks of about `size` characters.

    Paragraphs longer than `size` are split on sentence boundaries, then hard-split.
    Each chunk starts with the last `overlap` characters of the previous one so a fact
    that straddles a boundary is still retrievable.
    """
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n")).strip()
    if not text:
        return []

    pieces: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if len(para) <= size:
            pieces.append(para)
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", para):
            while len(sentence) > size:
                pieces.append(sentence[:size])
                sentence = sentence[size:]
            if sentence:
                pieces.append(sentence)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{piece}" if tail else piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks
