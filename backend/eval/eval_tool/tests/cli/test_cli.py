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


def test_cli_can_create_local_ner_template_without_external_authorization(tmp_path, write_metadata):
    metadata = tmp_path / "samples.xlsx"
    references = tmp_path / "ner_references.json"
    write_metadata(metadata, [(1, "wav", "001.wav", "Tekst referencyjny.")])

    status = main(
        ["--init-ner-references", "--metadata", str(metadata), "--ner-references", str(references)],
    )

    assert status == 0
    assert '"reviewed": false' in references.read_text(encoding="utf-8")


def test_cli_validates_references_without_external_authorization(tmp_path):
    validator_calls = []

    status = main(
        ["--validate-ner-references"],
        reference_validator=lambda *_args, **_kwargs: validator_calls.append(True) or 80,
        runtime_factory=lambda _args: pytest.fail("validation must not initialize a runtime"),
    )

    assert status == 0
    assert validator_calls == [True]


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


def test_cli_passes_score_ner_and_writes_aggregate_report(tmp_path):
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
            "ner": {"exact_record_rate": 1},
            "judge": {"mean_score": None},
            "errors": [],
        }

    status = main(
        [
            "--allow-external-data",
            "--no-judge",
            "--score-ner",
            "--samples",
            "001",
            "--output",
            str(report_path),
        ],
        dataset_loader=lambda *_args, **_kwargs: ["sample-001"],
        runtime_factory=lambda _args: SimpleNamespace(
            pipeline_factory=lambda: object(), resolved_config={"stt_model": "gpt-transcribe"}
        ),
        evaluator=fake_evaluator,
        report_writer=lambda report, path, **_kwargs: path,
        workbook_writer=lambda rows, path, **_kwargs: path,
    )

    assert status == 0
    assert calls["samples"] == ["sample-001"]
    assert calls["kwargs"]["judge_enabled"] is False
    assert calls["kwargs"]["include_details"] is False
    assert calls["kwargs"]["score_ner"] is True


def test_cli_skips_ner_references_and_writes_workbook_by_default(tmp_path):
    calls = {}

    def fake_evaluator(_samples, **kwargs):
        calls["score_ner"] = kwargs["score_ner"]
        return {
            "status": "complete",
            "samples_requested": 1,
            "pipeline_samples_completed": 1,
            "transcript": {"wer": 0, "cer": 0},
            "ner": {"exact_record_rate": None},
            "judge": {"mean_score": None},
            "errors": [],
            "review_rows": [{"sample_id": "001", "status": "complete"}],
        }

    status = main(
        ["--allow-external-data", "--no-judge", "--output", str(tmp_path / "result.json")],
        dataset_loader=lambda *_args, **kwargs: (
            calls.update(loader_kwargs=kwargs), ["sample"]
        )[1],
        runtime_factory=lambda _args: SimpleNamespace(
            pipeline_factory=lambda: object(), resolved_config={}
        ),
        evaluator=fake_evaluator,
        report_writer=lambda report, path, **_kwargs: path,
        workbook_writer=lambda rows, path, **kwargs: calls.update(
            workbook_rows=rows, workbook_path=path, workbook_kwargs=kwargs
        ) or path,
    )

    assert status == 0
    assert calls["loader_kwargs"]["score_ner"] is False
    assert calls["score_ner"] is False
    assert calls["workbook_rows"] == [{"sample_id": "001", "status": "complete"}]
    assert calls["workbook_path"].parent.name == "results"
    assert calls["workbook_path"].suffix == ".xlsx"
    assert calls["workbook_kwargs"]["include_ner_reference"] is False


def test_cli_fails_when_review_workbook_cannot_be_written(tmp_path):
    errors = []

    def fake_evaluator(_samples, **_kwargs):
        return {
            "status": "complete",
            "samples_requested": 1,
            "pipeline_samples_completed": 1,
            "transcript": {"wer": 0, "cer": 0},
            "ner": {"exact_record_rate": None},
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
