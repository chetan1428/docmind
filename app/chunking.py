"""Text extraction and chunking (LangChain text splitter)."""

import io

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf")


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type. Use one of: {', '.join(SUPPORTED_EXTENSIONS)}")


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Split on paragraphs, then sentences, then words, keeping chunks <= size characters."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    if not text.strip():
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator="end",
    )
    return [" ".join(c.split()) for c in splitter.split_text(text) if c.strip()]
