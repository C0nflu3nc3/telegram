from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from app.config import get_settings


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY не задан.")
    return OpenAI(api_key=settings.openai_api_key)


def create_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def create_embedding(text: str) -> list[float]:
    embeddings = create_embeddings([text])
    return embeddings[0]
