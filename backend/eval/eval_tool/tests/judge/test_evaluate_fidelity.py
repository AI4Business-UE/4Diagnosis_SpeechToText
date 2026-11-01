from eval_tool.judge import evaluate_fidelity


def test_fidelity_judge_receives_only_reference_and_corrected_transcript():
    request = {}

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    request.update(kwargs)

                    class Message:
                        content = '{"score": 4, "omissions": [], "additions": [], "contradictions": [], "rationale": "Faithful."}'

                    class Choice:
                        message = Message()

                    class Response:
                        choices = [Choice()]

                    return Response()

    result = evaluate_fidelity("gold text", "corrected text", "judge-model", client=FakeClient())

    assert result["score"] == 4
    message = request["messages"][1]["content"]
    assert "gold text" in message
    assert "corrected text" in message
    assert "raw transcript" not in message.lower()
