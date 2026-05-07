from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from app.utils.filters import SUPPORTED_DOCUMENT_EXTENSIONS


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_text_message(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        raise ValueError("Получен пустой текст.")
    return cleaned


def parse_file(file_path: Path) -> str:
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise ValueError("Поддерживаются только файлы TXT, PDF и DOCX.")

    if extension == ".txt":
        return _read_txt(file_path)
    if extension == ".pdf":
        return _read_pdf(file_path)
    if extension == ".docx":
        return _read_docx(file_path)

    raise ValueError("Неизвестный формат файла.")


def _read_txt(file_path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            return parse_text_message(file_path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    return parse_text_message(file_path.read_text(encoding="latin-1"))


def _read_pdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return parse_text_message("\n".join(pages))


def _read_docx(file_path: Path) -> str:
    try:
        from docx import Document as DocxDocument
    except Exception as error:
        raise RuntimeError(
            "Поддержка DOCX недоступна: установлен неверный пакет. "
            "Удалите `docx` и установите `python-docx`."
        ) from error

    document = DocxDocument(str(file_path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return parse_text_message("\n".join(paragraphs))
