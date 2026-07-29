"""Stack-trace embeddings. Default provider is Voyage AI. Set
EMBEDDING_PROVIDER=openai-compatible to point this at any OpenAI-compatible
embeddings endpoint instead, via EMBEDDING_BASE_URL + EMBEDDING_API_KEY +
EMBEDDING_MODEL.
"""

import os

import voyageai

PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "voyage")
VOYAGE_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-3.5")
OPENAI_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

_voyage_client: voyageai.Client | None = None
_openai_client = None


def has_credentials() -> bool:
    if PROVIDER == "openai-compatible":
        return bool(os.environ.get("EMBEDDING_API_KEY"))
    return bool(os.environ.get("VOYAGE_API_KEY"))


def _get_voyage_client() -> voyageai.Client:
    global _voyage_client
    if _voyage_client is None:
        _voyage_client = voyageai.Client()
    return _voyage_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai

        _openai_client = openai.OpenAI(
            base_url=os.environ.get("EMBEDDING_BASE_URL") or None,
            api_key=os.environ.get("EMBEDDING_API_KEY"),
        )
    return _openai_client


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if PROVIDER == "openai-compatible":
        result = _get_openai_client().embeddings.create(model=OPENAI_MODEL, input=texts)
        return [item.embedding for item in result.data]
    result = _get_voyage_client().embed(texts, model=VOYAGE_MODEL, input_type="document")
    return result.embeddings
