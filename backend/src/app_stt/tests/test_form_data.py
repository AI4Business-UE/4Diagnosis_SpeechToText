from app_stt.pipeline.form_data import build_form_data_from_entities


def test_build_form_data_from_entities_keeps_frontend_shape():
    entities = {
        "patient": {
            "first_name": "Jan",
            "last_name": "Nowak",
            "age": 42,
            "pesel": "84010112345",
        },
        "components": [{"name": "tarczyca"}, {"name": "węzeł chłonny"}],
    }

    form_data = build_form_data_from_entities(entities, "Opis po korekcie.")

    assert form_data == {
        "name": "Jan Nowak",
        "organ": "tarczyca, węzeł chłonny",
        "age": "42",
        "pesel": "84010112345",
        "description": "Opis po korekcie.",
    }


def test_build_form_data_uses_patient_metadata_as_fallback():
    entities = {
        "patient": {
            "first_name": "",
            "last_name": "",
            "age": "",
            "pesel": "",
        },
        "components": [],
    }
    metadata = {"name": "Anna Kowalska", "age": "35", "pesel": "91010112345"}

    form_data = build_form_data_from_entities(entities, "Opis.", metadata)

    assert form_data["name"] == "Anna Kowalska"
    assert form_data["age"] == "35"
    assert form_data["pesel"] == "91010112345"
    assert form_data["organ"] == ""
    assert form_data["description"] == "Opis."
