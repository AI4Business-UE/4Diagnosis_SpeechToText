import pytest
from eval_tool.dataset import validate_ner_references


def test_ner_reference_validator_checks_selected_coverage_without_audio(
    tmp_path, write_metadata, complete_reference, write_references
):
    metadata = tmp_path / "samples.xlsx"
    references = tmp_path / "ner_references.json"
    write_metadata(metadata, [(1, "wav", "001.wav", "Tekst 1"), (2, "wav", "002.wav", "Tekst 2")])
    write_references(references, {"001": complete_reference})

    assert validate_ner_references(metadata, references, sample_ids=["001"]) == 1
    with pytest.raises(ValueError, match="002"):
        validate_ner_references(metadata, references)
