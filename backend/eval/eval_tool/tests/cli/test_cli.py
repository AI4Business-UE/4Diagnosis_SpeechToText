from types import SimpleNamespace

import pytest
from eval_tool.cli import main


def test_cli_requires_explicit_external_data_authorization_before_runtime(tmp_path):
    runtime_calls = []

    with pytest.raises(SystemExit) as error:
        main(
            ["--no-judge", "--metadata", str(tmp_path / "missing.xlsx")],
            runtime_factory=lambda _args: runtime_calls.append(True),
        )

    assert error.value.code == 2
    assert runtime_calls == []


def test_cli_rejects_removed_gold_ner_scoring_flags(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(["--allow-external-data", "--no-judge", "--score-ner"])

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "Nieznane argumenty: --score-ner" in captured.err
    assert "unrecognized arguments" not in captured.err


def test_cli_keeps_detailed_reports_inside_the_ignored_results_directory(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--allow-external-data",
                "--no-judge",
                "--include-details",
                "--output",
                str(tmp_path / "clinical-details.json"),
            ]
        )

    assert error.value.code == 2


def test_cli_writes_aggregate_report_and_workbook_by_default(tmp_path):
    calls = {}
    report_path = tmp_path / "result.json"

    def fake_evaluator(samples, **kwargs):
        calls["samples"] = list(samples)
        calls["kwargs"] = kwargs
        return {
            "status": "complete",
            "samples_requested": len(calls["samples"]),
            "pipeline_samples_completed": len(calls["samples"]),
            "transcript": {"wer": 0, "cer": 0},
            "judge": {"mean_score": None},
            "errors": [],
            "review_rows": [{"sample_id": "001", "status": "complete"}],
        }

    status = main(
        [
            "--allow-external-data",
            "--no-judge",
            "--samples",
            "001",
            "--output",
            str(report_path),
        ],
        dataset_loader=lambda *_args, **kwargs: (
            calls.update(loader_kwargs=kwargs), ["sample-001"]
        )[1],
        runtime_factory=lambda _args: SimpleNamespace(
            pipeline_factory=lambda: object(), resolved_config={"stt_model": "gpt-transcribe"}
        ),
        evaluator=fake_evaluator,
        report_writer=lambda report, path, **_kwargs: path,
        workbook_writer=lambda rows, path, **kwargs: calls.update(
            workbook_rows=rows, workbook_path=path, workbook_kwargs=kwargs
        ) or path,
    )

    assert status == 0
    assert calls["samples"] == ["sample-001"]
    assert calls["kwargs"]["judge_enabled"] is False
    assert calls["kwargs"]["include_details"] is False
    assert calls["loader_kwargs"]["sample_ids"] == ["001"]
    assert calls["workbook_rows"] == [{"sample_id": "001", "status": "complete"}]
    assert calls["workbook_path"].parent.name == "results"
    assert calls["workbook_path"].suffix == ".xlsx"
    assert calls["workbook_kwargs"] == {}


def test_cli_summarizes_patient_metadata_mean_score(tmp_path):
    lines = []

    def fake_evaluator(_samples, **_kwargs):
        return {
            "status": "complete",
            "samples_requested": 2,
            "pipeline_samples_completed": 2,
            "transcript": {"wer": 0, "cer": 0},
            "patient_metadata": {"samples": 2, "mean_score": 0.625, "fields": {}},
            "judge": {"mean_score": None},
            "errors": [],
            "review_rows": [],
        }

    status = main(
        ["--allow-external-data", "--no-judge", "--output", str(tmp_path / "result.json")],
        dataset_loader=lambda *_args, **_kwargs: ["a", "b"],
        runtime_factory=lambda _args: SimpleNamespace(pipeline_factory=lambda: object(), resolved_config={}),
        evaluator=fake_evaluator,
        report_writer=lambda report, path, **_kwargs: path,
        workbook_writer=lambda rows, path, **_kwargs: path,
        output=lines.append,
    )

    assert status == 0
    assert any("metadane pacjenta: 0.625 (2 próbek)" in line for line in lines)


def test_cli_omits_patient_metadata_from_summary_without_graded_samples(tmp_path):
    lines = []

    def fake_evaluator(_samples, **_kwargs):
        return {
            "status": "complete",
            "samples_requested": 1,
            "pipeline_samples_completed": 1,
            "transcript": {"wer": 0, "cer": 0},
            "patient_metadata": {"samples": 0, "mean_score": None, "fields": {}},
            "judge": {"mean_score": None},
            "errors": [],
            "review_rows": [],
        }

    main(
        ["--allow-external-data", "--no-judge", "--output", str(tmp_path / "result.json")],
        dataset_loader=lambda *_args, **_kwargs: ["a"],
        runtime_factory=lambda _args: SimpleNamespace(pipeline_factory=lambda: object(), resolved_config={}),
        evaluator=fake_evaluator,
        report_writer=lambda report, path, **_kwargs: path,
        workbook_writer=lambda rows, path, **_kwargs: path,
        output=lines.append,
    )

    assert not any("metadane pacjenta" in line for line in lines)


def test_cli_fails_when_review_workbook_cannot_be_written(tmp_path):
    errors = []

    def fake_evaluator(_samples, **_kwargs):
        return {
            "status": "complete",
            "samples_requested": 1,
            "pipeline_samples_completed": 1,
            "transcript": {"wer": 0, "cer": 0},
            "judge": {"mean_score": None},
            "errors": [],
            "review_rows": [],
        }

    status = main(
        ["--allow-external-data", "--no-judge", "--output", str(tmp_path / "result.json")],
        dataset_loader=lambda *_args, **_kwargs: ["sample"],
        runtime_factory=lambda _args: SimpleNamespace(
            pipeline_factory=lambda: object(), resolved_config={}
        ),
        evaluator=fake_evaluator,
        report_writer=lambda report, path, **_kwargs: path,
        workbook_writer=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
        error_output=errors.append,
    )

    assert status == 1
    assert errors == ["Błąd ewaluacji (OSError); szczegóły pominięto ze względu na dane kliniczne."]
