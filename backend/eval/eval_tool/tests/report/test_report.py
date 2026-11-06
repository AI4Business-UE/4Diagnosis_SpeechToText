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
            "reference_text": "Tekst referencyjny",
            "transcript": "Surowy tekst",
            "entities": {"components": [{"name": "nerka"}]},
            "corrected_transcript": "Skorygowany tekst",
            "ner_reference": {"components": []},
            "judge_status": "judged",
            "judge_score": 3,
            "judge_rationale": "Małe pominięcie.",
            "judge_omissions": ["lewy bok", "dolny biegun"],
            "judge_additions": [],
            "judge_contradictions": ["prawa strona"],
        },
        {
            "sample_id": "002",
            "status": "failed",
            "reference_text": "Tekst referencyjny",
            "transcript": None,
            "entities": None,
            "corrected_transcript": None,
            "ner_reference": {"components": []},
            "judge_status": "not_run",
            "judge_opt_out_reason": None,
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
        "Tekst referencyjny",
        "Surowy transkrypt",
        "Skorygowany transkrypt",
        "Wynik NER (JSON)",
        "Status sędziego LLM",
        "Wynik sędziego LLM (0–4)",
        "Uzasadnienie sędziego LLM",
        "Pominięcia sędziego LLM",
        "Dodatki sędziego LLM",
        "Sprzeczności sędziego LLM",
        "Powód pominięcia sędziego",
        "Referencja Gold NER (JSON)",
    )
    assert values[1] == (
        "001",
        "niekompletna",
        "Tekst referencyjny",
        "Surowy tekst",
        '{"components": [{"name": "nerka"}]}',
        "Skorygowany tekst",
        "oceniono",
        3,
        "Małe pominięcie.",
        "lewy bok\ndolny biegun",
        None,
        "prawa strona",
        None,
        '{"components": []}',
    )
    assert values[2] == (
        "002", "nieudana", "Tekst referencyjny", None, None, None,
        "nie oceniono — błąd pipeline'u", None, None, None, None, None, None,
        '{"components": []}',
    )


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
        "Tekst referencyjny",
        "Surowy transkrypt",
        "Skorygowany transkrypt",
        "Wynik NER (JSON)",
        "Status sędziego LLM",
        "Wynik sędziego LLM (0–4)",
        "Uzasadnienie sędziego LLM",
        "Pominięcia sędziego LLM",
        "Dodatki sędziego LLM",
        "Sprzeczności sędziego LLM",
        "Powód pominięcia sędziego",
    )


def test_review_workbook_distinguishes_all_judge_statuses_and_exports_opt_out_reason(tmp_path):
    output = tmp_path / "review.xlsx"
    statuses = ["judged", "opted_out", "disabled", "error", "not_run"]
    rows = [
        {
            "sample_id": str(index),
            "status": "complete",
            "judge_status": status,
            "judge_opt_out_reason": "Powód oceny pominiętej" if status == "opted_out" else None,
        }
        for index, status in enumerate(statuses, start=1)
    ]

    save_review_workbook(rows, output)

    workbook = load_workbook(output, read_only=True, data_only=True)
    try:
        values = list(workbook.active.values)
    finally:
        workbook.close()
    judge_status_column = values[0].index("Status sędziego LLM")
    reason_column = values[0].index("Powód pominięcia sędziego")
    assert [row[judge_status_column] for row in values[1:]] == [
        "oceniono",
        "pominięto na poziomie próbki",
        "sędzia wyłączony globalnie",
        "błąd oceny sędziego",
        "nie oceniono — błąd pipeline'u",
    ]
    assert values[2][reason_column] == "Powód oceny pominiętej"
