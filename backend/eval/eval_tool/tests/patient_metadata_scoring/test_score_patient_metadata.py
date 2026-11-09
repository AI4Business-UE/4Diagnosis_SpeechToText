from eval_tool.patient_metadata_scoring import score_patient_metadata


def test_score_counts_each_reference_field_that_matches_the_extraction():
    reference = {"first_name": "Irena", "last_name": "Szymańska", "age": 66, "pesel": "58080899900"}
    extracted = {"first_name": "Irena", "last_name": "Szymańska", "age": 66, "pesel": "58080899900"}

    result = score_patient_metadata(reference, extracted)

    assert result == {
        "fields": {"first_name": 1, "last_name": 1, "age": 1, "pesel": 1},
        "score": 1.0,
    }


def test_names_match_case_insensitively_with_collapsed_whitespace():
    reference = {"first_name": "Irma Nowak", "last_name": None, "age": None, "pesel": None}
    extracted = {"first_name": "IRMA   nowak", "last_name": "Kowalska", "age": 5, "pesel": "12345678901"}

    result = score_patient_metadata(reference, extracted)

    assert result == {"fields": {"first_name": 1}, "score": 1.0}


def test_reference_fields_without_a_reference_value_are_not_graded():
    reference = {"first_name": None, "last_name": "Nowak", "age": None, "pesel": None}
    extracted = {"first_name": "Irma", "last_name": "Kowalska", "age": None, "pesel": None}

    result = score_patient_metadata(reference, extracted)

    assert result == {"fields": {"last_name": 0}, "score": 0.0}


def test_missing_extraction_of_a_reference_field_scores_zero():
    reference = {"first_name": "Irena", "last_name": "Szymańska", "age": 66, "pesel": "58080899900"}
    extracted = {"first_name": "Irena", "last_name": None, "age": 66, "pesel": None}

    result = score_patient_metadata(reference, extracted)

    assert result == {
        "fields": {"first_name": 1, "last_name": 0, "age": 1, "pesel": 0},
        "score": 0.5,
    }


def test_pipeline_failure_without_any_extraction_scores_all_reference_fields_zero():
    reference = {"first_name": "Irena", "last_name": None, "age": 66, "pesel": None}

    result = score_patient_metadata(reference, None)

    assert result == {"fields": {"first_name": 0, "age": 0}, "score": 0.0}


def test_reference_without_any_set_field_yields_no_score():
    reference = {"first_name": None, "last_name": None, "age": None, "pesel": None}

    assert score_patient_metadata(reference, {"first_name": "Irena"}) is None
