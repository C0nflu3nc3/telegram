from __future__ import annotations

from pathlib import Path


SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".pdf", ".docx"}


def is_supported_document(filename: str | None) -> bool:
    if not filename:
        return False
    return Path(filename).suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS
