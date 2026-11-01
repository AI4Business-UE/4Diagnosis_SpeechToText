import json

import pytest
from eval_tool.judge import (aggregate_judgements, evaluate_fidelity,
                             parse_judgement)


def test_judge_parses_a_bounded_fidelity_result():
    result = parse_judgement(
        json.dumps(
            {
                "score": 3,
                "omissions": ["one minor detail"],
                "additions": [],
                "contradictions": [],
                "rationale": "The main findings are preserved.",
            }
        )
    )

    assert result["score"] == 3
    assert result["omissions"] == ["one minor detail"]


def test_judge_rejects_scores_outside_the_agreed_scale():
    with pytest.raises(ValueError, match="0–4"):
        parse_judgement('{"score": 5, "omissions": [], "additions": [], "contradictions": [], "rationale": ""}')


def test_judge_uses_only_the_reference_and_corrected_transcript():
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


def test_judge_aggregation_reports_mean_distribution_and_issue_counts():
    aggregate = aggregate_judgements(
        [
            {"score": 4, "omissions": [], "additions": [], "contradictions": [], "rationale": ""},
            {"score": 2, "omissions": ["x"], "additions": ["y"], "contradictions": [], "rationale": ""},
        ]
    )

    assert aggregate["mean_score"] == 3
    assert aggregate["score_distribution"] == {"0": 0, "1": 0, "2": 1, "3": 0, "4": 1}
    assert aggregate["samples_with_omissions"] == 1
    assert aggregate["samples_with_additions"] == 1
