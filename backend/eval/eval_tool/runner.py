from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from .dataset import EvaluationSample
from .judge import aggregate_judgements, evaluate_fidelity
from .patient_metadata_scoring import (aggregate_patient_metadata_scores,
                                       score_patient_metadata)
from .transcript_scoring import aggregate_transcript_scores, score_transcript

_PATIENT_ROW_KEYS = {
    "first_name": "patient_first_name_result",
    "last_name": "patient_last_name_result",
    "age": "patient_age_result",
    "pesel": "patient_pesel_result",
}

_STAGE_LABELS = {
    "pipeline_setup": "inicjalizacji pipeline'u",
    "pipeline": "pełnego pipeline'u",
    "cleanup": "czyszczenia audio",
    "transcript_scoring": "oceny transkrypcji",
    "judge": "oceny sędziego LLM",
}


def run_evaluation(
    samples: Iterable[EvaluationSample],
    *,
    pipeline_factory: Callable[[], Any],
    judge: Callable[[str, str, str], Mapping[str, Any]] | None = None,
    judge_model: str | None = None,
    judge_enabled: bool = True,
    include_details: bool = False,
    resolved_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run selected recordings, score results, and retain aggregate results by default."""
    selected_samples = list(samples)
    if not selected_samples:
        raise ValueError("Brak próbek do ewaluacji.")
    if judge_enabled and not judge_model:
        raise ValueError("Włączona ocena LLM wymaga jawnie wskazanego modelu sędziego.")
    if judge_enabled and judge is None:
        judge = evaluate_fidelity

    started_at = datetime.now(timezone.utc).isoformat()
    try:
        pipeline = pipeline_factory()
    except Exception as error:
        errors = [_error(None, "pipeline_setup", error)]
        details = (
            [{"sample_id": sample.sample_id, "status": "failed"} for sample in selected_samples]
            if include_details
            else None
        )
        patient_metadata_scores: list[dict[str, Any]] = []
        failed_rows = []
        for sample in selected_samples:
            review_row = _review_row(
                sample.sample_id,
                reference_text=sample.reference_text,
                judge_opt_out_reason=sample.judge_opt_out_reason,
            )
            _apply_patient_metadata(review_row, sample, None, patient_metadata_scores)
            failed_rows.append(review_row)
        report = _build_report(
            selected_samples,
            started_at,
            0,
            errors,
            [],
            patient_metadata_scores,
            [],
            judge_enabled,
            judge_model,
            resolved_config,
            details,
        )
        report["review_rows"] = failed_rows
        return report

    errors = []
    transcript_scores: list[dict[str, Any]] = []
    patient_metadata_scores = []
    judgements: list[Mapping[str, Any]] = []
    details: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    pipeline_samples_completed = 0

    for sample in selected_samples:
        detail: dict[str, Any] = {"sample_id": sample.sample_id, "status": "failed"}
        sample_error_count = len(errors)
        pipeline_result: Mapping[str, Any] | None = None
        try:
            result = pipeline.run(str(sample.audio_path))
            if not isinstance(result, Mapping):
                raise ValueError("pipeline result is not an object")
            pipeline_result = result
            pipeline_samples_completed += 1
            detail["status"] = "complete"
        except Exception as error:  # a failed recording must not stop the remaining set
            errors.append(_error(sample.sample_id, "pipeline", error))
        finally:
            try:
                pipeline.cleanup(str(sample.audio_path))
            except Exception as error:  # cleanup failures also make the run incomplete
                errors.append(_error(sample.sample_id, "cleanup", error))

        if pipeline_result is None:
            review_row = _review_row(
                sample.sample_id,
                reference_text=sample.reference_text,
                judge_opt_out_reason=sample.judge_opt_out_reason,
            )
            _apply_patient_metadata(review_row, sample, None, patient_metadata_scores)
            review_rows.append(review_row)
            if include_details:
                details.append(detail)
            continue

        transcript = pipeline_result.get("transcript")
        corrected_transcript = pipeline_result.get("corrected_transcript")
        entities = pipeline_result.get("entities")
        review_row = _review_row(
            sample.sample_id,
            reference_text=sample.reference_text,
            judge_opt_out_reason=sample.judge_opt_out_reason,
        )
        review_row.update(
            {
                "status": detail["status"],
                "transcript": transcript,
                "entities": entities,
                "corrected_transcript": corrected_transcript,
            }
        )
        review_rows.append(review_row)
        _apply_patient_metadata(review_row, sample, entities, patient_metadata_scores)

        try:
            if not isinstance(transcript, str):
                raise ValueError("transcript is not a string")
            text_score = score_transcript(sample.reference_text, transcript)
            transcript_scores.append(text_score)
            detail["transcript_score"] = text_score
        except Exception as error:
            errors.append(_error(sample.sample_id, "transcript_scoring", error))

        if judge_enabled:
            if sample.judge_opt_out:
                review_row["judge_status"] = "opted_out"
            else:
                try:
                    if not isinstance(corrected_transcript, str):
                        raise ValueError("corrected_transcript is not a string")
                    assert judge is not None and judge_model is not None
                    judgement = judge(sample.reference_text, corrected_transcript, judge_model)
                    judgements.append(judgement)
                    detail["judge"] = judgement
                    review_row["judge_status"] = "judged"
                    review_row.update(_review_judgement(judgement))
                except Exception as error:
                    review_row["judge_status"] = "error"
                    errors.append(_error(sample.sample_id, "judge", error))
        else:
            review_row["judge_status"] = "disabled"

        if len(errors) > sample_error_count:
            review_row["status"] = "incomplete"
            detail["status"] = "incomplete"

        if include_details:
            detail.update(
                {
                    "reference_text": sample.reference_text,
                    "transcript": transcript,
                    "corrected_transcript": corrected_transcript,
                    "entities": entities,
                    "retrieved_templates": pipeline_result.get("retrieved_templates"),
                    "preprocessing": pipeline_result.get("preprocessing"),
                }
            )
            details.append(detail)

    report = _build_report(
        selected_samples,
        started_at,
        pipeline_samples_completed,
        errors,
        transcript_scores,
        patient_metadata_scores,
        judgements,
        judge_enabled,
        judge_model,
        resolved_config,
        details if include_details else None,
    )
    report["review_rows"] = review_rows
    return report


def _review_row(
    sample_id: str,
    *,
    reference_text: str | None = None,
    judge_opt_out_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "status": "failed",
        "reference_text": reference_text,
        "transcript": None,
        "entities": None,
        "corrected_transcript": None,
        "judge_status": "not_run",
        "judge_score": None,
        "judge_rationale": None,
        "judge_omissions": None,
        "judge_additions": None,
        "judge_contradictions": None,
        "judge_opt_out_reason": judge_opt_out_reason,
        "patient_first_name_result": None,
        "patient_last_name_result": None,
        "patient_age_result": None,
        "patient_pesel_result": None,
        "patient_metadata_score": None,
    }


def _apply_patient_metadata(
    review_row: dict[str, Any],
    sample: EvaluationSample,
    entities: Any,
    patient_metadata_scores: list[dict[str, Any]],
) -> None:
    """Grade the raw NER patient extraction against the workbook metadata reference."""
    reference = {
        "first_name": sample.patient_first_name,
        "last_name": sample.patient_last_name,
        "age": sample.patient_age,
        "pesel": sample.patient_pesel,
    }
    if all(value is None for value in reference.values()):
        return
    extracted = entities.get("patient") if isinstance(entities, Mapping) else None
    if not isinstance(extracted, Mapping):
        extracted = None
    result = score_patient_metadata(reference, extracted)
    if result is None:
        return
    for field, row_key in _PATIENT_ROW_KEYS.items():
        review_row[row_key] = result["fields"].get(field)
    review_row["patient_metadata_score"] = result["score"]
    patient_metadata_scores.append(result)


def _review_judgement(judgement: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "judge_score": judgement["score"],
        "judge_rationale": judgement["rationale"],
        "judge_omissions": judgement["omissions"],
        "judge_additions": judgement["additions"],
        "judge_contradictions": judgement["contradictions"],
    }


def _build_report(
    selected_samples: list[EvaluationSample],
    started_at: str,
    pipeline_samples_completed: int,
    errors: list[dict[str, str | None]],
    transcript_scores: list[dict[str, Any]],
    patient_metadata_scores: list[dict[str, Any]],
    judgements: list[Mapping[str, Any]],
    judge_enabled: bool,
    judge_model: str | None,
    resolved_config: Mapping[str, Any] | None,
    details: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "complete" if not errors else "incomplete",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "samples_requested": len(selected_samples),
        "pipeline_samples_completed": pipeline_samples_completed,
        "errors": errors,
        "pipeline_config": dict(resolved_config or {}),
        "transcript": aggregate_transcript_scores(transcript_scores),
        "patient_metadata": aggregate_patient_metadata_scores(patient_metadata_scores),
        "judge": {
            **aggregate_judgements(judgements),
            "model": judge_model if judge_enabled else None,
            "samples_opted_out": sum(sample.judge_opt_out for sample in selected_samples),
        },
    }
    if details is not None:
        report["details"] = details
    return report


def _error(sample_id: str | None, stage: str, error: Exception) -> dict[str, str | None]:
    # Exception messages can contain provider payloads or clinical text; keep the
    # default aggregate report limited to safe identifiers and exception types.
    return {
        "sample_id": sample_id,
        "stage": stage,
        "error_type": type(error).__name__,
        "message": f"Wystąpił błąd na etapie: {_STAGE_LABELS.get(stage, 'ewaluacji')}.",
    }
