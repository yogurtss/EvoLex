from evolex.agents.deepseek_client import DeepSeekExtractor


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
