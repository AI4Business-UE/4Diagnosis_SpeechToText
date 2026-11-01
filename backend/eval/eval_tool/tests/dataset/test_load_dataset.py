import pytest
from eval_tool.dataset import load_dataset


def test_dataset_loads_workbook_rows_and_reviewed_references(
    tmp_path, write_metadata, complete_reference, write_references
):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    write_metadata(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])
    references = tmp_path / "ner_references.json"
    write_references(references, {"001": complete_reference})

    samples = load_dataset(metadata, audio, references, score_ner=True)

    assert len(samples) == 1
    assert samples[0].sample_id == "001"
    assert samples[0].reference_text == "Próbka referencyjna."
    assert samples[0].audio_path == audio / "001.wav"
    assert samples[0].ner_reference["components"] == []


def test_dataset_does_not_require_ner_references_unless_scoring_is_enabled(
    tmp_path, write_metadata
):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    write_metadata(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])

    samples = load_dataset(metadata, audio, tmp_path / "missing-ner-references.json")

    assert len(samples) == 1
    assert samples[0].ner_reference is None


def test_dataset_rejects_missing_ner_references_for_selected_samples(
    tmp_path, write_metadata, complete_reference, write_references
):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    (audio / "002.wav").touch()
    write_metadata(metadata, [(1, "wav", "001.wav", "Tekst 1"), (2, "wav", "002.wav", "Tekst 2")])
    references = tmp_path / "ner_references.json"
    write_references(references, {"001": complete_reference})

    with pytest.raises(ValueError, match="002"):
        load_dataset(metadata, audio, references, score_ner=True)


def test_dataset_can_select_a_subset_before_validating_references(
    tmp_path, write_metadata, complete_reference, write_references
):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    (audio / "002.wav").touch()
    write_metadata(metadata, [(1, "wav", "001.wav", "Tekst 1"), (2, "wav", "002.wav", "Tekst 2")])
    references = tmp_path / "ner_references.json"
    write_references(references, {"001": complete_reference})

    samples = load_dataset(metadata, audio, references, sample_ids=["001"], score_ner=True)

    assert [sample.sample_id for sample in samples] == ["001"]


def test_dataset_rejects_measurements_without_a_known_unit(
    tmp_path, write_metadata, complete_reference, write_references
):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    write_metadata(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])
    reference = complete_reference
    reference["entities"]["components"] = [{"name": "nerka", "dim_x": 4.0}]
    references = tmp_path / "ner_references.json"
    write_references(references, {"001": reference})

    with pytest.raises(ValueError, match="jednostkę cm lub mm"):
        load_dataset(metadata, audio, references, score_ner=True)


def test_dataset_rejects_an_empty_patient_annotation(
    tmp_path, write_metadata, complete_reference, write_references
):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    write_metadata(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])
    reference = complete_reference
    reference["entities"]["patient"] = {}
    references = tmp_path / "ner_references.json"
    write_references(references, {"001": reference})

    with pytest.raises(ValueError, match="patient.*pusta"):
        load_dataset(metadata, audio, references, score_ner=True)
