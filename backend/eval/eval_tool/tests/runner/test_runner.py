from pathlib import Path

from eval_tool.dataset import EvaluationSample
from eval_tool.runner import run_evaluation


def _sample(sample_id):
    return EvaluationSample(
        sample_id=sample_id,
        audio_path=Path(f"{sample_id}.wav"),
        reference_text="kot ma psa",
        ner_reference={
            "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
            "components": [],
            "lesions": [],
            "fluid_samples": [],
        },
    )


class FakePipeline:
    def __init__(self, failures=None):
        self.failures = failures or set()
        self.cleaned = []

    def run(self, audio_path):
        sample_id = Path(audio_path).stem
        if sample_id in self.failures:
            raise RuntimeError("provider failure")
        return {
            "transcript": "kot ma psa",
            "corrected_transcript": "kot ma psa",
            "entities": {
                "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
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


def test_evaluation_retains_review_outputs_without_details_or_ner_scoring():
    pipeline = FakePipeline(failures={"001"})
    failed_sample = _sample("001")
    successful_sample = _sample("002")
    failed_sample = EvaluationSample(
        sample_id=failed_sample.sample_id,
        audio_path=failed_sample.audio_path,
        reference_text=failed_sample.reference_text,
        ner_reference=None,
    )
    successful_sample = EvaluationSample(
        sample_id=successful_sample.sample_id,
        audio_path=successful_sample.audio_path,
        reference_text=successful_sample.reference_text,
        ner_reference=None,
    )

    report = run_evaluation(
        [failed_sample, successful_sample],
        pipeline_factory=lambda: pipeline,
        judge_enabled=False,
    )

    assert report["ner"]["records"] == 0
    assert report["review_rows"] == [
        {
            "sample_id": "001",
            "status": "failed",
            "transcript": None,
            "entities": None,
            "corrected_transcript": None,
        },
        {
            "sample_id": "002",
            "status": "complete",
            "transcript": "kot ma psa",
            "entities": {
                "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
                "components": [],
                "lesions": [],
                "fluid_samples": [],
            },
            "corrected_transcript": "kot ma psa",
        },
    ]


def test_ner_scoring_is_opt_in_and_keeps_gold_reference_for_review():
    report = run_evaluation(
        [_sample("001")],
        pipeline_factory=FakePipeline,
        judge_enabled=False,
        score_ner=True,
    )

    assert report["ner"]["records"] == 1
    assert report["ner"]["exact_record_rate"] == 1
    assert report["review_rows"][0]["ner_reference"] == _sample("001").ner_reference


def test_ner_scoring_failure_keeps_pipeline_outputs_for_review():
    class InvalidEntitiesPipeline(FakePipeline):
        def run(self, audio_path):
            result = super().run(audio_path)
            result["entities"] = {"unexpected": True}
            return result

    report = run_evaluation(
        [_sample("001")],
        pipeline_factory=InvalidEntitiesPipeline,
        judge_enabled=False,
        score_ner=True,
    )

    assert report["status"] == "incomplete"
    assert report["errors"][0]["stage"] == "ner_scoring"
    assert report["review_rows"][0]["status"] == "incomplete"
    assert report["review_rows"][0]["transcript"] == "kot ma psa"
    assert report["review_rows"][0]["entities"] == {"unexpected": True}


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
    assert report["details"][0]["ner_reference"] == _sample("001").ner_reference


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
        score_ner=True,
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
    assert [row["ner_reference"] for row in report["review_rows"]] == [
        _sample("001").ner_reference,
        _sample("002").ner_reference,
    ]
