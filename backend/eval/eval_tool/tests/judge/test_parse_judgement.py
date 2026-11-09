import json

import pytest
from eval_tool.judge import parse_judgement


def test_judge_parser_accepts_a_bounded_fidelity_result():
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


def test_judge_parser_rejects_scores_outside_the_agreed_scale():
    with pytest.raises(ValueError, match="0–4"):
        parse_judgement('{"score": 5, "omissions": [], "additions": [], "contradictions": [], "rationale": ""}')
