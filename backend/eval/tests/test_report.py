import json

from eval_tool.report import save_report


def test_report_saves_aggregate_json_without_per_sample_details_by_default(tmp_path):
    report = {
        "status": "complete",
        "transcript": {"wer": 0.1},
        "details": [{"reference_text": "clinical text", "transcript": "output"}],
    }
    output = tmp_path / "aggregate.json"

    saved_path = save_report(report, output)

    assert saved_path == output
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["transcript"]["wer"] == 0.1
    assert "details" not in saved
    assert "clinical text" not in output.read_text(encoding="utf-8")


def test_report_includes_details_only_when_explicitly_enabled(tmp_path):
    output = tmp_path / "detailed.json"

    save_report(
        {"status": "complete", "details": [{"reference_text": "clinical text"}]},
        output,
        include_details=True,
    )

    assert json.loads(output.read_text(encoding="utf-8"))["details"][0]["reference_text"] == "clinical text"
