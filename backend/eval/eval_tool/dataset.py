from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

_REQUIRED_COLUMNS = ("id", "format", "nazwa pliku", "tekst referencyjny")
_JUDGE_ENABLED_COLUMN = "oceniaj sędzią LLM"
_JUDGE_OPT_OUT_REASON_COLUMN = "powód pominięcia sędziego"
_FIRST_NAME_COLUMN = "imię pacjenta"
_LAST_NAME_COLUMN = "nazwisko pacjenta"
_AGE_COLUMN = "wiek"
_PESEL_COLUMN = "PESEL"
_PESEL_PATTERN = re.compile(r"[0-9]{11}")
_AGE_PATTERN = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class EvaluationSample:
    sample_id: str
    audio_path: Path
    reference_text: str
    judge_opt_out: bool = False
    judge_opt_out_reason: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_age: int | None = None
    patient_pesel: str | None = None


def load_dataset(
    metadata_path: str | Path,
    audio_dir: str | Path,
    sample_ids: list[str] | None = None,
) -> list[EvaluationSample]:
    """Load selected recordings with their reference text and patient metadata."""
    metadata = _read_metadata(Path(metadata_path))
    selected_ids = _select_ids(metadata, sample_ids)
    audio_root = Path(audio_dir)

    samples: list[EvaluationSample] = []
    for sample_id in selected_ids:
        row = metadata[sample_id]
        audio_path = _audio_path(audio_root, sample_id, row["filename"], row["format"])
        if not audio_path.is_file():
            raise ValueError(f"Nie znaleziono pliku audio dla próbki {sample_id}: {audio_path}")
        samples.append(
            EvaluationSample(
                sample_id=sample_id,
                audio_path=audio_path,
                reference_text=row["reference_text"],
                judge_opt_out=row["judge_opt_out"],
                judge_opt_out_reason=row["judge_opt_out_reason"],
                patient_first_name=row["patient_first_name"],
                patient_last_name=row["patient_last_name"],
                patient_age=row["patient_age"],
                patient_pesel=row["patient_pesel"],
            )
        )

    return samples


def _read_metadata(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"Nie znaleziono arkusza metadanych: {path}")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = next(rows, None)
        if not headers:
            raise ValueError(f"Arkusz metadanych nie zawiera wiersza nagłówków: {path}")
        indexes = {str(value).strip(): index for index, value in enumerate(headers) if value is not None}
        missing_columns = [column for column in _REQUIRED_COLUMNS if column not in indexes]
        if missing_columns:
            raise ValueError(f"Brak wymaganych kolumn w arkuszu metadanych: {', '.join(missing_columns)}")

        metadata: dict[str, dict[str, Any]] = {}
        for row_number, row in enumerate(rows, start=2):
            raw_id = _cell(row, indexes["id"])
            if raw_id is None or str(raw_id).strip() == "":
                continue
            sample_id = _normalize_sample_id(raw_id)
            if sample_id in metadata:
                raise ValueError(f"Powtórzony identyfikator próbki '{sample_id}' w wierszu {row_number} arkusza")

            reference_text = _cell(row, indexes["tekst referencyjny"])
            if not isinstance(reference_text, str) or not reference_text.strip():
                raise ValueError(f"Brak tekstu referencyjnego dla próbki {sample_id}")
            judge_enabled = (
                _cell(row, indexes[_JUDGE_ENABLED_COLUMN])
                if _JUDGE_ENABLED_COLUMN in indexes
                else None
            )
            if judge_enabled is not None and not isinstance(judge_enabled, bool):
                raise ValueError(
                    f"Kolumna '{_JUDGE_ENABLED_COLUMN}' dla próbki {sample_id} "
                    "musi zawierać wartość logiczną lub być pusta"
                )
            opt_out_reason = (
                _cell(row, indexes[_JUDGE_OPT_OUT_REASON_COLUMN])
                if _JUDGE_OPT_OUT_REASON_COLUMN in indexes
                else None
            )
            if opt_out_reason is not None and not isinstance(opt_out_reason, str):
                raise ValueError(
                    f"Kolumna '{_JUDGE_OPT_OUT_REASON_COLUMN}' dla próbki {sample_id} "
                    "musi zawierać tekst lub być pusta"
                )
            normalized_reason = opt_out_reason.strip() if isinstance(opt_out_reason, str) else ""
            judge_opt_out = judge_enabled is False
            if normalized_reason and not judge_opt_out:
                raise ValueError(
                    f"Powód pominięcia sędziego dla próbki {sample_id} jest dozwolony "
                    "tylko gdy próbka jest wyłączona z oceny"
                )
            metadata[sample_id] = {
                "format": str(_cell(row, indexes["format"]) or "").strip(),
                "filename": str(_cell(row, indexes["nazwa pliku"]) or "").strip(),
                "reference_text": reference_text.strip(),
                "judge_opt_out": judge_opt_out,
                "judge_opt_out_reason": normalized_reason or None,
                "patient_first_name": _text_cell(row, indexes, _FIRST_NAME_COLUMN),
                "patient_last_name": _text_cell(row, indexes, _LAST_NAME_COLUMN),
                "patient_age": _age_cell(row, indexes, _AGE_COLUMN, sample_id),
                "patient_pesel": _pesel_cell(row, indexes, _PESEL_COLUMN, sample_id),
            }
        if not metadata:
            raise ValueError(f"Arkusz metadanych nie zawiera próbek: {path}")
        return metadata
    finally:
        workbook.close()


def _select_ids(metadata: dict[str, Any], requested: list[str] | None) -> list[str]:
    if requested is None:
        return sorted(metadata)
    selected = [_normalize_sample_id(sample_id) for sample_id in requested]
    if len(selected) != len(set(selected)):
        raise ValueError("Wybór próbek zawiera powtórzone identyfikatory")
    unknown = sorted(set(selected) - metadata.keys())
    if unknown:
        raise ValueError(f"Nieznane identyfikatory próbek: {', '.join(unknown)}")
    return selected


def _audio_path(audio_dir: Path, sample_id: str, filename: str, file_format: str) -> Path:
    if filename:
        candidate_name = Path(filename)
        if candidate_name.name != filename or filename in {".", ".."}:
            raise ValueError(f"Nieprawidłowa nazwa pliku audio dla próbki {sample_id}: {filename!r}")
        if not candidate_name.suffix:
            extension = file_format.strip().lstrip(".")
            if not extension:
                raise ValueError(f"Brak formatu audio dla próbki {sample_id}")
            candidate_name = candidate_name.with_suffix(f".{extension}")
    else:
        extension = file_format.strip().lstrip(".")
        if not extension:
            raise ValueError(f"Brak nazwy pliku lub formatu audio dla próbki {sample_id}")
        candidate_name = Path(f"{sample_id}.{extension}")
    return audio_dir / candidate_name


def _normalize_sample_id(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit():
        return text.zfill(3)
    if not text or any(character in text for character in "/\\"):
        raise ValueError(f"Nieprawidłowy identyfikator próbki: {value!r}")
    return text


def _cell(row: tuple[Any, ...], index: int) -> Any:
    return row[index] if index < len(row) else None


def _optional_cell(row: tuple[Any, ...], indexes: dict[str, int], column: str) -> Any:
    if column not in indexes:
        return None
    return _cell(row, indexes[column])


def _text_cell(row: tuple[Any, ...], indexes: dict[str, int], column: str) -> str | None:
    value = _optional_cell(row, indexes, column)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _age_cell(row: tuple[Any, ...], indexes: dict[str, int], column: str, sample_id: str) -> int | None:
    invalid = ValueError(f"Kolumna '{column}' dla próbki {sample_id} musi być liczbą całkowitą")
    value = _optional_cell(row, indexes, column)
    if value is None:
        return None
    if isinstance(value, bool):
        raise invalid
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if not _AGE_PATTERN.fullmatch(text):
            raise invalid
        return int(text)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, int):
        return value
    raise invalid


def _pesel_cell(row: tuple[Any, ...], indexes: dict[str, int], column: str, sample_id: str) -> str | None:
    invalid = ValueError(f"Kolumna '{column}' dla próbki {sample_id} musi zawierać 11 cyfr")
    value = _optional_cell(row, indexes, column)
    if value is None:
        return None
    if isinstance(value, bool):
        raise invalid
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int):
        # Excel numeric cells drop leading zeros; restore them up to the 11-digit length.
        digits = str(value).zfill(11)
    else:
        digits = str(value).strip()
        if not digits:
            return None
    if not _PESEL_PATTERN.fullmatch(digits):
        raise invalid
    return digits
