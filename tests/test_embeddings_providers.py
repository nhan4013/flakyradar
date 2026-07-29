from types import SimpleNamespace

from core import embeddings


def test_has_credentials_voyage(monkeypatch):
    monkeypatch.setattr(embeddings, "PROVIDER", "voyage")
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    assert embeddings.has_credentials() is False
    monkeypatch.setenv("VOYAGE_API_KEY", "key")
    assert embeddings.has_credentials() is True


def test_has_credentials_openai_compatible(monkeypatch):
    monkeypatch.setattr(embeddings, "PROVIDER", "openai-compatible")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    assert embeddings.has_credentials() is False
    monkeypatch.setenv("EMBEDDING_API_KEY", "key")
    assert embeddings.has_credentials() is True


def test_embed_texts_openai_compatible(monkeypatch):
    monkeypatch.setattr(embeddings, "PROVIDER", "openai-compatible")

    class FakeClient:
        class embeddings:
            @staticmethod
            def create(**kwargs):
                return SimpleNamespace(
                    data=[SimpleNamespace(embedding=[0.1, 0.2]), SimpleNamespace(embedding=[0.3, 0.4])]
                )

    monkeypatch.setattr(embeddings, "_get_openai_client", lambda: FakeClient())
    result = embeddings.embed_texts(["a", "b"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_texts_empty_list_short_circuits():
    assert embeddings.embed_texts([]) == []
