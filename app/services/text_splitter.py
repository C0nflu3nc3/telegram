from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    content: str
    word_count: int


def split_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("Размер чанка должен быть больше нуля.")
    if overlap < 0:
        raise ValueError("Overlap не может быть отрицательным.")
    if overlap >= chunk_size:
        raise ValueError("Overlap должен быть меньше размера чанка.")

    words = text.split()
    if not words:
        return []

    chunks: list[TextChunk] = []
    step = chunk_size - overlap
    start = 0
    index = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(
            TextChunk(
                index=index,
                content=" ".join(chunk_words),
                word_count=len(chunk_words),
            )
        )
        if end >= len(words):
            break
        start += step
        index += 1

    return chunks
