"""Document ingestion — extract text, chunk, embed, and upsert to Qdrant."""

import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.engine import RagEngine

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX file."""
    doc = DocxDocument(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())


def extract_text_from_text(file_bytes: bytes) -> str:
    """Extract text from plain text / markdown files."""
    return file_bytes.decode("utf-8", errors="replace")


def extract_text_from_image(file_bytes: bytes) -> str:
    """OCR text from an image (scanned letters etc.) via Tesseract (Indonesian + English)."""
    import pytesseract
    from PIL import Image

    image = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(image, lang="ind+eng")


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> list[str]:
    """Split text into chunks using LangChain's RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


async def ingest_document(
    rag: RagEngine,
    file_name: str,
    file_bytes: bytes,
    document_id: str,
    source: str = "",
    category: str | None = None,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> int:
    """
    Full ingestion pipeline: extract → chunk → embed → upsert.
    Returns number of chunks created.
    """
    ext = Path(file_name).suffix.lower()

    # Extract text based on file type
    if ext == ".pdf":
        text = extract_text_from_pdf(file_bytes)
    elif ext == ".docx":
        text = extract_text_from_docx(file_bytes)
    elif ext in (".txt", ".md"):
        text = extract_text_from_text(file_bytes)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"):
        text = extract_text_from_image(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if not text.strip():
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"):
            raise ValueError("Tidak ada teks terdeteksi pada gambar")
        raise ValueError("No text extracted from document")

    # Chunk
    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    logger.info(f"Created {len(chunks)} chunks from '{file_name}'")

    # Prepare metadata
    metadatas = [
        {
            "document_id": document_id,
            "source": source or file_name,
            "chunk_index": i,
            "category": category,
        }
        for i in range(len(chunks))
    ]

    # Embed + upsert (async)
    await rag.upsert_chunks(chunks, metadatas)

    return len(chunks)
