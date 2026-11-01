import json

from eval_tool.dataset import initialize_reference_template


def test_reference_template_contains_every_sample_and_starts_unreviewed(tmp_path, write_metadata):
    metadata = tmp_path / "samples.xlsx"
    output = tmp_path / "ner_references.json"
    write_metadata(metadata, [(1, "wav", "001.wav", "Text 1"), (2, "wav", "002.wav", "Text 2")])

    initialize_reference_template(metadata, output)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert sorted(data["samples"]) == ["001", "002"]
    assert all(not item["reviewed"] for item in data["samples"].values())
