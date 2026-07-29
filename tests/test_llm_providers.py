from core import llm


def test_has_credentials_anthropic(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.has_credentials() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    assert llm.has_credentials() is True


def test_has_credentials_openai_compatible(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai-compatible")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert llm.has_credentials() is False
    monkeypatch.setenv("LLM_API_KEY", "key")
    assert llm.has_credentials() is True


class _FakeOpenAIClient:
    def __init__(self, content):
        self._content = content
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        from types import SimpleNamespace

        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_classify_root_cause_openai_compatible(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai-compatible")
    payload = (
        '{"category": "network", "confidence": 0.6, '
        '"explanation": "timeout", "suggested_fix": "add retry"}'
    )
    monkeypatch.setattr(llm, "_get_openai_client", lambda: _FakeOpenAIClient(payload))

    result = llm.classify_root_cause("t::x", "trace", "msg")
    assert result["category"] == "network"
    assert result["confidence"] == 0.6


def test_classify_root_cause_openai_compatible_strips_markdown_fence(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai-compatible")
    payload = (
        "```json\n"
        '{"category": "unknown", "confidence": 0.1, "explanation": "x", "suggested_fix": ""}'
        "\n```"
    )
    monkeypatch.setattr(llm, "_get_openai_client", lambda: _FakeOpenAIClient(payload))

    result = llm.classify_root_cause("t::x", "trace", "msg")
    assert result["category"] == "unknown"


def test_classify_root_cause_openai_compatible_falls_back_on_bad_json(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai-compatible")
    monkeypatch.setattr(llm, "_get_openai_client", lambda: _FakeOpenAIClient("not json at all"))

    result = llm.classify_root_cause("t::x", "trace", "msg")
    assert result["category"] == "unknown"
    assert result["confidence"] == 0.0


def test_suggest_fix_openai_compatible(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai-compatible")
    payload = '{"suggestion": "use a lock", "confidence": 0.8}'
    monkeypatch.setattr(llm, "_get_openai_client", lambda: _FakeOpenAIClient(payload))

    result = llm.suggest_fix("t::x", "trace", "msg", [{"commit_sha": "abc", "description": "d"}])
    assert result["suggestion"] == "use a lock"


def test_suggest_fix_skips_llm_call_without_similar_fixes(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "openai-compatible")

    def boom():
        raise AssertionError("should not call the LLM with no similar fixes")

    monkeypatch.setattr(llm, "_get_openai_client", boom)
    result = llm.suggest_fix("t::x", "trace", "msg", [])
    assert result == {"suggestion": "", "confidence": 0.0}
