from pathlib import Path

from eval_tool.dataset import EvaluationSample
from eval_tool.runner import run_evaluation


def _sample(sample_id):
    return EvaluationSample(
        sample_id=sample_id,
        audio_path=Path(f"{sample_id}.wav"),
        reference_text="kot ma psa",
    )


def _sample_with_judge_opt_out(sample_id, reason=None):
    sample = _sample(sample_id)
    return EvaluationSample(
        sample_id=sample.sample_id,
        audio_path=sample.audio_path,
        reference_text=sample.reference_text,
        judge_opt_out=True,
        judge_opt_out_reason=reason,
    )


def _sample_with_patient_metadata(sample_id):
    sample = _sample(sample_id)
    return EvaluationSample(
        sample_id=sample.sample_id,
        audio_path=sample.audio_path,
        reference_text=sample.reference_text,
        patient_first_name="Irena",
        patient_last_name="Szymańska",
        patient_age=66,
        patient_pesel="58080899900",
    )


class FakePipeline:
    def __init__(self, failures=None, patients=None):
        self.failures = failures or set()
        self.patients = patients or {}
        self.cleaned = []

    def run(self, audio_path):
        sample_id = Path(audio_path).stem
        if sample_id in self.failures:
            raise RuntimeError("provider failure")
        return {
            "transcript": "kot ma psa",
            "corrected_transcript": "kot ma psa",
            "entities": {
                "patient": self.patients.get(
                    sample_id, {"first_name": None, "last_name": None, "pesel": None, "age": None}
                ),
                "components": [],
                "lesions": [],
                "fluid_samples": [],
            },
            "retrieved_templates": [],
            "preprocessing": {"status": "ok"},
        }

    def cleanup(self, audio_path):
        self.cleaned.append(str(audio_path))


def test_evaluation_continues_after_pipeline_failure_and_captures_review_outputs():
    pipeline = FakePipeline(failures={"001"})

    report = run_evaluation(
        [_sample("001"), _sample("002")],
        pipeline_factory=lambda: pipeline,
        judge_enabled=False,
    )

    assert report["status"] == "incomplete"
    assert report["samples_requested"] == 2
    assert report["pipeline_samples_completed"] == 1
    assert report["errors"][0]["sample_id"] == "001"
    assert report["transcript"]["wer"] == 0
    assert pipeline.cleaned == ["001.wav", "002.wav"]
    assert "details" not in report
    assert report["review_rows"][1]["transcript"] == "kot ma psa"


def test_evaluation_retains_review_outputs_without_details():
    pipeline = FakePipeline(failures={"001"})

    report = run_evaluation(
        [_sample("001"), _sample("002")],
        pipeline_factory=lambda: pipeline,
        judge_enabled=False,
    )

    assert report["review_rows"] == [
        {
            "sample_id": "001",
            "status": "failed",
            "reference_text": "kot ma psa",
            "transcript": None,
            "entities": None,
            "corrected_transcript": None,
            "judge_status": "not_run",
            "judge_score": None,
            "judge_rationale": None,
            "judge_omissions": None,
            "judge_additions": None,
            "judge_contradictions": None,
            "judge_opt_out_reason": None,
            "patient_first_name_result": None,
            "patient_last_name_result": None,
            "patient_age_result": None,
            "patient_pesel_result": None,
            "patient_metadata_score": None,
        },
        {
            "sample_id": "002",
            "status": "complete",
            "reference_text": "kot ma psa",
            "transcript": "kot ma psa",
            "entities": {
                "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
                "components": [],
                "lesions": [],
                "fluid_samples": [],
            },
            "corrected_transcript": "kot ma psa",
            "judge_status": "disabled",
            "judge_score": None,
            "judge_rationale": None,
            "judge_omissions": None,
            "judge_additions": None,
            "judge_contradictions": None,
            "judge_opt_out_reason": None,
            "patient_first_name_result": None,
            "patient_last_name_result": None,
            "patient_age_result": None,
            "patient_pesel_result": None,
            "patient_metadata_score": None,
        },
    ]


def test_evaluation_runs_judge_and_includes_sensitive_details_only_on_request():
    pipeline = FakePipeline()
    judge_calls = []

    def judge(reference, corrected, model):
        judge_calls.append((reference, corrected, model))
        return {
            "score": 4,
            "omissions": [],
            "additions": [],
            "contradictions": [],
            "rationale": "Faithful.",
        }

    report = run_evaluation(
        [_sample("001")],
        pipeline_factory=lambda: pipeline,
        judge=judge,
        judge_model="judge-model",
        include_details=True,
    )

    assert judge_calls == [("kot ma psa", "kot ma psa", "judge-model")]
    assert report["judge"]["mean_score"] == 4
    assert report["details"][0]["reference_text"] == "kot ma psa"
    assert report["details"][0]["judge"]["rationale"] == "Faithful."
    assert report["details"][0]["preprocessing"]["status"] == "ok"


def test_judge_opt_out_keeps_pipeline_results_but_excludes_sample_from_judge_aggregate():
    pipeline = FakePipeline()
    judge_calls = []

    def judge(*args):
        judge_calls.append(args)
        return {
            "score": 4,
            "omissions": [],
            "additions": [],
            "contradictions": [],
            "rationale": "Faithful.",
        }

    report = run_evaluation(
        [_sample_with_judge_opt_out("001", "Brak zgody")],
        pipeline_factory=lambda: pipeline,
        judge=judge,
        judge_model="judge-model",
    )

    assert judge_calls == []
    assert report["status"] == "complete"
    assert report["pipeline_samples_completed"] == 1
    assert report["judge"]["samples"] == 0
    assert report["judge"]["samples_opted_out"] == 1
    assert report["judge"]["mean_score"] is None
    assert pipeline.cleaned == ["001.wav"]
    assert report["review_rows"][0]["judge_status"] == "opted_out"
    assert report["review_rows"][0]["judge_opt_out_reason"] == "Brak zgody"
    assert report["review_rows"][0]["judge_score"] is None


def test_global_judge_disable_and_pipeline_failure_have_distinct_judge_statuses():
    report = run_evaluation(
        [_sample("001"), _sample_with_judge_opt_out("002", "Powód")],
        pipeline_factory=lambda: FakePipeline(failures={"002"}),
        judge_enabled=False,
    )

    assert [row["judge_status"] for row in report["review_rows"]] == ["disabled", "not_run"]
    assert report["judge"]["samples_opted_out"] == 1


def test_judge_failure_marks_run_incomplete_without_discarding_stt_scores():
    pipeline = FakePipeline()

    def failing_judge(*_args):
        raise RuntimeError("judge unavailable")

    report = run_evaluation(
        [_sample("001")],
        pipeline_factory=lambda: pipeline,
        judge=failing_judge,
        judge_model="judge-model",
    )

    assert report["status"] == "incomplete"
    assert report["transcript"]["wer"] == 0
    assert report["errors"][0]["stage"] == "judge"


def test_pipeline_factory_failure_returns_an_incomplete_report():
    def failing_factory():
        raise RuntimeError("pipeline setup failed")

    report = run_evaluation(
        [_sample("001"), _sample("002")],
        pipeline_factory=failing_factory,
        judge_enabled=False,
        include_details=True,
    )

    assert report["status"] == "incomplete"
    assert report["samples_requested"] == 2
    assert report["pipeline_samples_completed"] == 0
    assert report["errors"][0]["stage"] == "pipeline_setup"
    assert report["errors"][0]["sample_id"] is None
    assert report["errors"][0]["error_type"] == "RuntimeError"
    assert "pipeline setup failed" not in report["errors"][0]["message"]
    assert report["transcript"]["wer"] is None
    assert [detail["status"] for detail in report["details"]] == ["failed", "failed"]
    assert [row["status"] for row in report["review_rows"]] == ["failed", "failed"]


def test_patient_metadata_is_graded_against_workbook_reference_deterministically():
    pipeline = FakePipeline(
        patients={"001": {"first_name": "IRENA", "last_name": "Nowak", "age": 66, "pesel": None}}
    )

    report = run_evaluation(
        [_sample_with_patient_metadata("001")],
        pipeline_factory=lambda: pipeline,
        judge_enabled=False,
    )

    assert report["patient_metadata"] == {
        "samples": 1,
        "mean_score": 0.5,
        "fields": {
            "first_name": {"correct": 1, "graded": 1},
            "last_name": {"correct": 0, "graded": 1},
            "age": {"correct": 1, "graded": 1},
            "pesel": {"correct": 0, "graded": 1},
        },
    }
    row = report["review_rows"][0]
    assert row["patient_first_name_result"] == 1
    assert row["patient_last_name_result"] == 0
    assert row["patient_age_result"] == 1
    assert row["patient_pesel_result"] == 0
    assert row["patient_metadata_score"] == 0.5


def test_samples_without_patient_metadata_leave_row_cells_empty_and_skipped_from_mean():
    pipeline = FakePipeline(
        patients={"001": {"first_name": "Irena", "last_name": "Szymańska", "age": 66, "pesel": "58080899900"}}
    )

    report = run_evaluation(
        [_sample("001"), _sample_with_patient_metadata("002")],
        pipeline_factory=lambda: pipeline,
        judge_enabled=False,
    )

    assert report["patient_metadata"]["samples"] == 1
    assert report["patient_metadata"]["mean_score"] == 0.0
    assert report["review_rows"][0]["patient_metadata_score"] is None
    assert report["review_rows"][0]["patient_first_name_result"] is None
    # sample 002 has a reference but the pipeline extracted nothing for it
    assert report["review_rows"][1]["patient_first_name_result"] == 0
    assert report["review_rows"][1]["patient_metadata_score"] == 0.0


def test_failed_pipeline_scores_patient_metadata_reference_fields_as_zero():
    pipeline = FakePipeline(failures={"001"})

    report = run_evaluation(
        [_sample_with_patient_metadata("001")],
        pipeline_factory=lambda: pipeline,
        judge_enabled=False,
    )

    assert report["patient_metadata"] == {
        "samples": 1,
        "mean_score": 0.0,
        "fields": {
            "first_name": {"correct": 0, "graded": 1},
            "last_name": {"correct": 0, "graded": 1},
            "age": {"correct": 0, "graded": 1},
            "pesel": {"correct": 0, "graded": 1},
        },
    }
    row = report["review_rows"][0]
    assert row["patient_metadata_score"] == 0.0


def test_only_reference_fields_present_in_the_workbook_are_graded_per_sample():
    sample = EvaluationSample(
        sample_id="001",
        audio_path=Path("001.wav"),
        reference_text="kot ma psa",
        patient_first_name="Irena",
    )
    pipeline = FakePipeline(patients={"001": {"first_name": "Irena", "age": 33}})

    report = run_evaluation([sample], pipeline_factory=lambda: pipeline, judge_enabled=False)

    row = report["review_rows"][0]
    assert row["patient_first_name_result"] == 1
    assert row["patient_last_name_result"] is None
    assert row["patient_age_result"] is None
    assert row["patient_pesel_result"] is None
    assert row["patient_metadata_score"] == 1.0
    assert report["patient_metadata"]["samples"] == 1


def test_run_without_any_patient_metadata_reports_no_graded_samples():
    report = run_evaluation(
        [_sample("001")],
        pipeline_factory=FakePipeline,
        judge_enabled=False,
    )

    assert report["patient_metadata"] == {"samples": 0, "mean_score": None, "fields": {}}


def test_malformed_patient_extraction_does_not_abort_the_run():
    class MalformedPatientPipeline(FakePipeline):
        def run(self, audio_path):
            result = super().run(audio_path)
            result["entities"]["patient"] = ["Irena"]
            return result

    report = run_evaluation(
        [_sample_with_patient_metadata("001"), _sample_with_patient_metadata("002")],
        pipeline_factory=MalformedPatientPipeline,
        judge_enabled=False,
    )

    assert report["status"] == "complete"
    assert report["patient_metadata"]["samples"] == 2
    assert report["patient_metadata"]["mean_score"] == 0.0
