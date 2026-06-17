from evolex.agents.deepseek_client import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLMConfig,
    chat_completion_kwargs,
    DeepSeekExtractor,
)


class _FakeMessage:
    content = '[{"type":"entity","text":"API","evidence":"API Gateway","confidence":0.9}]'


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


class _FakeCompletions:
    def create(self, **_kwargs):
        return _FakeResponse()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


def test_deepseek_extractor_emits_model_logs() -> None:
    events: list[tuple[str, str]] = []
    extractor = DeepSeekExtractor.__new__(DeepSeekExtractor)
    extractor.api_key = "test-key"
    extractor.base_url = "https://api.deepseek.com"
    extractor.model = "deepseek-v4-flash"
    extractor.timeout_seconds = 30
    extractor.on_event = lambda stage, message: events.append((stage, message))
    extractor.client = _FakeClient()

    atoms = extractor.extract("API Gateway retries HTTP 503 responses.")

    assert atoms[0]["text"] == "API"
    assert ("llm", "Semantic extraction parsed 1 atoms.") in events
    assert any("Semantic extraction model output" in message for _stage, message in events)


def test_deepseek_profile_keeps_thinking_parameters() -> None:
    config = LLMConfig(base_url=DEEPSEEK_BASE_URL, model=DEEPSEEK_MODEL)

    kwargs = chat_completion_kwargs(
        config,
        [{"role": "user", "content": "hello"}],
        reasoning_effort="high",
        thinking_type="enabled",
    )

    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


def test_generic_profile_omits_deepseek_parameters() -> None:
    config = LLMConfig(base_url="http://localhost:8000/v1", model="qwen3.5-397b")

    kwargs = chat_completion_kwargs(
        config,
        [{"role": "user", "content": "hello"}],
        reasoning_effort="high",
        thinking_type="enabled",
    )

    assert kwargs == {
        "model": "qwen3.5-397b",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
    }


def test_local_generic_model_allows_keyless() -> None:
    config = LLMConfig(base_url="http://127.0.0.1:8000/v1", model="qwen3.5-397b")

    assert config.inferred_profile() == "generic"
    assert config.effective_api_key() == "local-openai-compatible"


def test_llm_config_supports_new_and_legacy_env_keys(monkeypatch) -> None:
    monkeypatch.delenv("EVOLEX_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    assert LLMConfig().resolved_api_key() == "legacy-key"

    monkeypatch.setenv("EVOLEX_API_KEY", "new-key")
    assert LLMConfig().resolved_api_key() == "new-key"
