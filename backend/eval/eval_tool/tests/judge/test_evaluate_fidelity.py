import sys
from types import SimpleNamespace

from eval_tool.runtime import BACKEND_DIR
from eval_tool.judge import evaluate_fidelity

# Bramę LLM testuje się tu bez Django — grube reeksporty pakietu app_stt
# są leniwe, więc sam moduł gateway importuje się offline.
sys.path.insert(0, str(BACKEND_DIR / "src"))

_JUDGEMENT = '{"score": 4, "omissions": [], "additions": [], "contradictions": [], "rationale": "Faithful."}'


class FakeClient:
    def __init__(self, request):
        self._request = request

        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)

    def _create(self, **kwargs):
        self._request.update(kwargs)
        message = SimpleNamespace(content=_JUDGEMENT)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_fidelity_judge_receives_only_reference_and_corrected_transcript(monkeypatch):
    monkeypatch.delenv("LLM_HOST", raising=False)
    request = {}

    result = evaluate_fidelity(
        "gold text", "corrected text", "judge-model", client=FakeClient(request)
    )

    assert result["score"] == 4
    message = request["messages"][1]["content"]
    assert "gold text" in message
    assert "corrected text" in message
    assert "raw transcript" not in message.lower()


def test_judge_passes_model_reference_untouched_on_default_openrouter_host(monkeypatch):
    monkeypatch.delenv("LLM_HOST", raising=False)
    request = {}

    evaluate_fidelity("gold", "corrected", "openai/gpt-4o-mini", client=FakeClient(request))

    assert request["model"] == "openai/gpt-4o-mini"


def test_judge_resolves_model_reference_via_gateway_on_openai_host(monkeypatch):
    monkeypatch.setenv("LLM_HOST", "openai")
    request = {}

    evaluate_fidelity("gold", "corrected", "openai/gpt-4o-mini", client=FakeClient(request))

    assert request["model"] == "gpt-4o-mini"
