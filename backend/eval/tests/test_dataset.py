import json

import pytest
from eval_tool.dataset import initialize_reference_template, load_dataset
from openpyxl import Workbook


def _write_workbook(path, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["id", "format", "nazwa pliku", "tekst referencyjny"])
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def _complete_reference():
    return {
        "reviewed": True,
        "entities": {
            "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
            "components": [],
            "lesions": [],
            "fluid_samples": [],
        },
    }


def test_dataset_loads_workbook_rows_and_reviewed_references(tmp_path):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    _write_workbook(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])
    references = tmp_path / "ner_references.json"
    references.write_text(
        json.dumps({"version": 1, "samples": {"001": _complete_reference()}}),
        encoding="utf-8",
    )

    samples = load_dataset(metadata, audio, references)

    assert len(samples) == 1
    assert samples[0].sample_id == "001"
    assert samples[0].reference_text == "Próbka referencyjna."
    assert samples[0].audio_path == audio / "001.wav"
    assert samples[0].ner_reference["components"] == []


def test_dataset_rejects_missing_or_unreviewed_ner_references(tmp_path):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    (audio / "002.wav").touch()
    _write_workbook(
        metadata,
        [(1, "wav", "001.wav", "Tekst 1"), (2, "wav", "002.wav", "Tekst 2")],
    )
    references = tmp_path / "ner_references.json"
    references.write_text(
        json.dumps({"version": 1, "samples": {"001": _complete_reference()}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="002"):
        load_dataset(metadata, audio, references)


def test_dataset_can_select_a_subset_before_validating_references(tmp_path):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    (audio / "002.wav").touch()
    _write_workbook(
        metadata,
        [(1, "wav", "001.wav", "Tekst 1"), (2, "wav", "002.wav", "Tekst 2")],
    )
    references = tmp_path / "ner_references.json"
    references.write_text(
        json.dumps({"version": 1, "samples": {"001": _complete_reference()}}),
        encoding="utf-8",
    )

    samples = load_dataset(metadata, audio, references, sample_ids=["001"])

    assert [sample.sample_id for sample in samples] == ["001"]


def test_dataset_initializes_a_human_review_template_for_every_sample(tmp_path):
    metadata = tmp_path / "samples.xlsx"
    output = tmp_path / "ner_references.json"
    _write_workbook(metadata, [(1, "wav", "001.wav", "Text 1"), (2, "wav", "002.wav", "Text 2")])

    initialize_reference_template(metadata, output)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert sorted(data["samples"]) == ["001", "002"]
    assert all(not item["reviewed"] for item in data["samples"].values())


def test_dataset_rejects_measurements_without_a_known_unit(tmp_path):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    _write_workbook(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])
    reference = _complete_reference()
    reference["entities"]["components"] = [{"name": "nerka", "dim_x": 4.0}]
    references = tmp_path / "ner_references.json"
    references.write_text(
        json.dumps({"version": 1, "samples": {"001": reference}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="jednostkę cm lub mm"):
        load_dataset(metadata, audio, references)


def test_dataset_rejects_an_empty_patient_annotation(tmp_path):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    _write_workbook(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])
    reference = _complete_reference()
    reference["entities"]["patient"] = {}
    references = tmp_path / "ner_references.json"
    references.write_text(
        json.dumps({"version": 1, "samples": {"001": reference}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="patient.*pusta"):
        load_dataset(metadata, audio, references)
