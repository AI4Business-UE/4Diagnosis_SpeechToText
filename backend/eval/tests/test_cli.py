from types import SimpleNamespace

import pytest
from eval_tool.cli import main
from openpyxl import Workbook


def _metadata(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["id", "format", "nazwa pliku", "tekst referencyjny"])
    sheet.append([1, "wav", "001.wav", "Tekst referencyjny."])
    workbook.save(path)


def test_cli_requires_explicit_external_data_authorization_before_runtime(tmp_path):
    runtime_calls = []

    with pytest.raises(SystemExit) as error:
        main(
            ["--no-judge", "--metadata", str(tmp_path / "missing.xlsx")],
            runtime_factory=lambda _args: runtime_calls.append(True),
        )

    assert error.value.code == 2
    assert runtime_calls == []


def test_cli_can_create_local_ner_template_without_external_authorization(tmp_path):
    metadata = tmp_path / "samples.xlsx"
    references = tmp_path / "ner_references.json"
    _metadata(metadata)

    status = main(
        ["--init-ner-references", "--metadata", str(metadata), "--ner-references", str(references)],
    )

    assert status == 0
    assert '"reviewed": false' in references.read_text(encoding="utf-8")


def test_cli_runs_no_judge_mode_with_injected_runtime_and_writes_aggregate_report(tmp_path):
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
    )

    assert status == 0
    assert calls["samples"] == ["sample-001"]
    assert calls["kwargs"]["judge_enabled"] is False
    assert calls["kwargs"]["include_details"] is False
