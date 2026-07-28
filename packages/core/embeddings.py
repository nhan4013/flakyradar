"""Stack-trace embeddings via Voyage AI. Swap the client here if the provider changes."""

import os

import voyageai

MODEL = os.environ.get("VOYAGE_MODEL", "voyage-3.5")

_client: voyageai.Client | None = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client()
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    result = _get_client().embed(texts, model=MODEL, input_type="document")
    return result.embeddings
