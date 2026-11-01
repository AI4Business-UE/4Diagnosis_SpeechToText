import json

from openpyxl import load_workbook

from eval_tool.report import save_report, save_review_workbook


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


def test_report_never_saves_review_rows_to_aggregate_json_even_with_details(tmp_path):
    output = tmp_path / "detailed.json"
    report = {
        "status": "complete",
        "details": [{"reference_text": "clinical text"}],
        "review_rows": [{"transcript": "sensitive transcript"}],
    }

    save_report(report, output, include_details=True)

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["details"][0]["reference_text"] == "clinical text"
    assert "review_rows" not in saved
    assert "sensitive transcript" not in output.read_text(encoding="utf-8")


def test_review_workbook_writes_polish_columns_and_one_row_per_sample(tmp_path):
    output = tmp_path / "results" / "review.xlsx"
    rows = [
        {
            "sample_id": "001",
            "status": "incomplete",
            "transcript": "Surowy tekst",
            "entities": {"components": [{"name": "nerka"}]},
            "corrected_transcript": "Skorygowany tekst",
            "ner_reference": {"components": []},
        },
        {
            "sample_id": "002",
            "status": "failed",
            "transcript": None,
            "entities": None,
            "corrected_transcript": None,
            "ner_reference": {"components": []},
        },
    ]

    saved_path = save_review_workbook(rows, output, include_ner_reference=True)

    workbook = load_workbook(saved_path, read_only=True, data_only=True)
    try:
        values = list(workbook.active.values)
    finally:
        workbook.close()
    assert values[0] == (
        "Identyfikator próbki",
        "Status",
        "Surowy transkrypt",
        "Wynik NER (JSON)",
        "Skorygowany transkrypt",
        "Referencja Gold NER (JSON)",
    )
    assert values[1] == (
        "001",
        "niekompletna",
        "Surowy tekst",
        '{"components": [{"name": "nerka"}]}',
        "Skorygowany tekst",
        '{"components": []}',
    )
    assert values[2] == ("002", "nieudana", None, None, None, '{"components": []}')


def test_review_workbook_omits_gold_reference_column_when_ner_scoring_is_disabled(tmp_path):
    output = tmp_path / "review.xlsx"

    save_review_workbook([], output)

    workbook = load_workbook(output, read_only=True, data_only=True)
    try:
        headers = next(workbook.active.values)
    finally:
        workbook.close()
    assert headers == (
        "Identyfikator próbki",
        "Status",
        "Surowy transkrypt",
        "Wynik NER (JSON)",
        "Skorygowany transkrypt",
    )
