from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .reference_schema import (NER_ENTITY_FIELDS, NER_FIELD_TYPES,
                               NER_MEASUREMENT_FIELDS)

_REQUIRED_COLUMNS = ("id", "format", "nazwa pliku", "tekst referencyjny")
_JUDGE_ENABLED_COLUMN = "oceniaj sędzią LLM"
_JUDGE_OPT_OUT_REASON_COLUMN = "powód pominięcia sędziego"


@dataclass(frozen=True)
class EvaluationSample:
    sample_id: str
    audio_path: Path
    reference_text: str
    ner_reference: dict[str, Any] | None
    judge_opt_out: bool = False
    judge_opt_out_reason: str | None = None


def load_dataset(
    metadata_path: str | Path,
    audio_dir: str | Path,
    ner_references_path: str | Path,
    sample_ids: list[str] | None = None,
    *,
    score_ner: bool = False,
) -> list[EvaluationSample]:
    """Load selected recordings and optionally require reviewed NER references."""
    metadata = _read_metadata(Path(metadata_path))
    selected_ids = _select_ids(metadata, sample_ids)
    references = (
        _validated_references(metadata, selected_ids, Path(ner_references_path))
        if score_ner
        else {}
    )
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
                ner_reference=references.get(sample_id),
                judge_opt_out=row["judge_opt_out"],
                judge_opt_out_reason=row["judge_opt_out_reason"],
            )
        )

    return samples


def validate_ner_references(
    metadata_path: str | Path,
    ner_references_path: str | Path,
    sample_ids: list[str] | None = None,
) -> int:
    """Validate reviewed NER coverage without requiring audio or contacting services."""
    metadata = _read_metadata(Path(metadata_path))
    selected_ids = _select_ids(metadata, sample_ids)
    _validated_references(metadata, selected_ids, Path(ner_references_path))
    return len(selected_ids)


def initialize_reference_template(
    metadata_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Create a local, unreviewed reference skeleton without copying clinical text."""
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"Plik referencji NER już istnieje; nie nadpisano: {output}")

    metadata = _read_metadata(Path(metadata_path))
    template = {
        "version": 1,
        "samples": {
            sample_id: {"reviewed": False, "entities": None}
            for sample_id in sorted(metadata)
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


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
            }
        if not metadata:
            raise ValueError(f"Arkusz metadanych nie zawiera próbek: {path}")
        return metadata
    finally:
        workbook.close()


def _read_ner_references(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(
            f"Nie znaleziono pliku referencji NER: {path}. "
            "Utwórz lokalny szablon poleceniem eval CLI przed uruchomieniem."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Plik referencji NER nie zawiera poprawnego JSON: {path}") from error
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("samples"), dict):
        raise ValueError("Plik referencji NER musi zawierać version=1 oraz obiekt samples")

    normalized: dict[str, Any] = {}
    for raw_id, entry in data["samples"].items():
        sample_id = _normalize_sample_id(raw_id)
        if sample_id in normalized:
            raise ValueError(f"Powtórzony znormalizowany identyfikator próbki '{sample_id}' w referencjach NER")
        normalized[sample_id] = entry
    return normalized


def _validated_references(
    metadata: dict[str, dict[str, str]],
    selected_ids: list[str],
    reference_path: Path,
) -> dict[str, dict[str, Any]]:
    references = _read_ner_references(reference_path)
    unknown_ids = sorted(references.keys() - metadata.keys())
    if unknown_ids:
        raise ValueError(f"Nieznane identyfikatory w referencjach NER: {', '.join(unknown_ids)}")
    missing_ids = [sample_id for sample_id in selected_ids if sample_id not in references]
    if missing_ids:
        raise ValueError(
            f"Brak sprawdzonych referencji NER dla próbek: {', '.join(missing_ids)}. "
            "Utwórz lokalny szablon poleceniem eval CLI i uzupełnij go przed uruchomieniem."
        )
    return {
        sample_id: _validate_reference(sample_id, references[sample_id])
        for sample_id in selected_ids
    }


def _validate_reference(sample_id: str, entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict) or entry.get("reviewed") is not True:
        raise ValueError(f"Referencja NER dla próbki {sample_id} nie jest oznaczona jako sprawdzona")
    entities = entry.get("entities")
    if not isinstance(entities, dict):
        raise ValueError(f"Referencja NER dla próbki {sample_id} nie zawiera obiektu entities")
    missing = set(NER_ENTITY_FIELDS) - entities.keys()
    if missing:
        raise ValueError(
            f"Referencja NER dla próbki {sample_id} nie zawiera kategorii: "
            f"{', '.join(sorted(missing))}"
        )
    extra_categories = entities.keys() - NER_ENTITY_FIELDS.keys()
    if extra_categories:
        raise ValueError(
            f"Referencja NER dla próbki {sample_id} zawiera nieznane kategorie: "
            f"{', '.join(sorted(extra_categories))}"
        )
    if not isinstance(entities["patient"], dict):
        raise ValueError(f"Kategoria patient w referencji próbki {sample_id} musi być obiektem")
    if not entities["patient"]:
        raise ValueError(
            f"Kategoria patient w referencji próbki {sample_id} jest pusta; "
            "dla znanych brakujących atrybutów użyj jawnych wartości null"
        )
    for category in ("components", "lesions", "fluid_samples"):
        if not isinstance(entities[category], list):
            raise ValueError(f"Kategoria {category} w referencji próbki {sample_id} musi być tablicą")
    for category, allowed_fields in NER_ENTITY_FIELDS.items():
        values = [entities[category]] if category == "patient" else entities[category]
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise ValueError(f"Wartość {category}[{index}] w referencji próbki {sample_id} musi być obiektem")
            unknown = set(value) - allowed_fields
            if unknown:
                raise ValueError(
                    f"Wartość {category}[{index}] w referencji próbki {sample_id} zawiera nieznane pola: "
                    f"{', '.join(sorted(unknown))}"
                )
            if not value:
                raise ValueError(f"Wartość {category}[{index}] w referencji próbki {sample_id} jest pusta")
            if category != "patient" and not any(field_value is not None for field_value in value.values()):
                raise ValueError(
                    f"Wartość {category}[{index}] w referencji próbki {sample_id} "
                    "nie ma znanego atrybutu; dla braku encji użyj pustej tablicy kategorii"
                )
            for field, field_value in value.items():
                _validate_field_value(sample_id, category, index, field, field_value)
            if category in {"components", "lesions"}:
                has_measurement = any(
                    value.get(field) is not None
                    for field in NER_MEASUREMENT_FIELDS
                )
                if has_measurement and value.get("unit") not in {"cm", "mm"}:
                    raise ValueError(
                        f"Wartość {category}[{index}] w referencji próbki {sample_id} "
                        "musi zawierać jednostkę cm lub mm przy wymiarach"
                    )
    return entities


def _validate_field_value(sample_id: str, category: str, index: int, field: str, value: Any) -> None:
    if value is None:
        return
    expected_type = NER_FIELD_TYPES[category][field]
    valid = isinstance(value, expected_type) and not (
        isinstance(value, bool) and expected_type != bool
    )
    if not valid:
        raise ValueError(
            f"Pole {category}[{index}].{field} w referencji próbki {sample_id} ma nieprawidłowy typ"
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(
            f"Pole {category}[{index}].{field} w referencji próbki {sample_id} musi być skończoną liczbą"
        )
    if field == "unit" and value not in {"cm", "mm"}:
        raise ValueError(f"Jednostka w referencji próbki {sample_id} musi być cm lub mm")
    if field == "clarity" and value not in {"klarowny", "mętny"}:
        raise ValueError(f"Pole clarity w referencji próbki {sample_id} ma nieprawidłową wartość")
    if field == "component_index" and value < 0:
        raise ValueError(f"Pole component_index w referencji próbki {sample_id} nie może być ujemne")
    if field == "features" and any(not isinstance(item, str) for item in value):
        raise ValueError(f"Pole features w referencji próbki {sample_id} musi zawierać teksty")


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
