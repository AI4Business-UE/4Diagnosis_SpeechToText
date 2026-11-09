import pytest
from eval_tool.dataset import load_dataset

METADATA_HEADERS = ["id", "format", "nazwa pliku", "tekst referencyjny"]
PATIENT_HEADERS = METADATA_HEADERS + ["imię pacjenta", "nazwisko pacjenta", "wiek", "PESEL"]
JUDGE_HEADERS = METADATA_HEADERS + ["oceniaj sędzią LLM", "powód pominięcia sędziego"]


def _prepare(tmp_path):
    """Return fresh metadata and audio paths with one sample's audio file present."""
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    return metadata, audio


def test_dataset_loads_workbook_rows(tmp_path, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(metadata, [(1, "wav", "001.wav", "Próbka referencyjna.")])

    samples = load_dataset(metadata, audio)

    assert len(samples) == 1
    assert samples[0].sample_id == "001"
    assert samples[0].reference_text == "Próbka referencyjna."
    assert samples[0].audio_path == audio / "001.wav"
    assert samples[0].judge_opt_out is False
    assert samples[0].judge_opt_out_reason is None
    assert samples[0].patient_first_name is None
    assert samples[0].patient_last_name is None
    assert samples[0].patient_age is None
    assert samples[0].patient_pesel is None


@pytest.mark.parametrize("value", ["sześćdziesiąt", "66,5", 66.5, True])
def test_dataset_rejects_non_integer_patient_age(tmp_path, value, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", None, None, value, None)],
        headers=PATIENT_HEADERS,
    )

    with pytest.raises(ValueError, match=r"Kolumna 'wiek' dla próbki 001 musi być liczbą całkowitą"):
        load_dataset(metadata, audio)


@pytest.mark.parametrize("value", ["5808089990", "5808089990A", "58 080 899 90", "abc"])
def test_dataset_rejects_patient_pesel_without_eleven_digits(tmp_path, value, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", None, None, None, value)],
        headers=PATIENT_HEADERS,
    )

    with pytest.raises(ValueError, match=r"Kolumna 'PESEL' dla próbki 001 musi zawierać 11 cyfr"):
        load_dataset(metadata, audio)


def test_dataset_pads_numeric_patient_pesel_to_eleven_digits(tmp_path, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", None, None, None, 8291361116)],
        headers=PATIENT_HEADERS,
    )

    samples = load_dataset(metadata, audio)

    assert samples[0].patient_pesel == "08291361116"


@pytest.mark.parametrize("value", [123456789012, "58080899900 0"])
def test_dataset_rejects_patient_pesel_longer_than_eleven_digits(tmp_path, value, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", None, None, None, value)],
        headers=PATIENT_HEADERS,
    )

    with pytest.raises(ValueError, match=r"Kolumna 'PESEL' dla próbki 001 musi zawierać 11 cyfr"):
        load_dataset(metadata, audio)


@pytest.mark.parametrize("value", ["٣٣", "٥٥٥٥٥٥٥٥٥٥٥"])
def test_dataset_rejects_non_ascii_digits_in_patient_metadata(tmp_path, value, write_metadata):
    is_age = value == "٣٣"
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", None, None, value if is_age else None, None if is_age else value)],
        headers=PATIENT_HEADERS,
    )

    expected = (
        r"Kolumna 'wiek' dla próbki 001 musi być liczbą całkowitą"
        if is_age
        else r"Kolumna 'PESEL' dla próbki 001 musi zawierać 11 cyfr"
    )
    with pytest.raises(ValueError, match=expected):
        load_dataset(metadata, audio)


def test_dataset_reads_patient_metadata_columns(tmp_path, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", " Irena ", "Szymańska", 66, "58080899900")],
        headers=PATIENT_HEADERS,
    )

    samples = load_dataset(metadata, audio)

    assert samples[0].patient_first_name == "Irena"
    assert samples[0].patient_last_name == "Szymańska"
    assert samples[0].patient_age == 66
    assert samples[0].patient_pesel == "58080899900"


def test_dataset_treats_empty_and_blank_patient_cells_as_unset(tmp_path, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", "", "   ", " ", "")],
        headers=PATIENT_HEADERS,
    )

    samples = load_dataset(metadata, audio)

    assert samples[0].patient_first_name is None
    assert samples[0].patient_last_name is None
    assert samples[0].patient_age is None
    assert samples[0].patient_pesel is None


def test_dataset_can_select_a_subset(tmp_path, write_metadata):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    (audio / "002.wav").touch()
    write_metadata(metadata, [(1, "wav", "001.wav", "Tekst 1"), (2, "wav", "002.wav", "Tekst 2")])

    samples = load_dataset(metadata, audio, sample_ids=["001"])

    assert [sample.sample_id for sample in samples] == ["001"]


def test_dataset_reads_optional_judge_opt_out_and_reason_without_changing_defaults(
    tmp_path, write_metadata
):
    metadata = tmp_path / "samples.xlsx"
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "001.wav").touch()
    (audio / "002.wav").touch()
    write_metadata(
        metadata,
        [
            [1, "wav", "001.wav", "Tekst 1", False, "Brak zgody na ocenę LLM"],
            [2, "wav", "002.wav", "Tekst 2", None, None],
        ],
        headers=JUDGE_HEADERS,
    )

    samples = load_dataset(metadata, audio)

    assert [(sample.judge_opt_out, sample.judge_opt_out_reason) for sample in samples] == [
        (True, "Brak zgody na ocenę LLM"),
        (False, None),
    ]


@pytest.mark.parametrize("value", ["FALSE", 0, 1, "tak"])
def test_dataset_rejects_non_boolean_judge_opt_out_values(tmp_path, value, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", value)],
        headers=JUDGE_HEADERS[:5],
    )

    with pytest.raises(ValueError, match="wartość logiczną"):
        load_dataset(metadata, audio)


@pytest.mark.parametrize("opt_out", [None, True])
def test_dataset_rejects_opt_out_reason_without_explicit_opt_out(tmp_path, opt_out, write_metadata):
    metadata, audio = _prepare(tmp_path)
    write_metadata(
        metadata,
        [(1, "wav", "001.wav", "Tekst", opt_out, "Powód")],
        headers=JUDGE_HEADERS,
    )

    with pytest.raises(ValueError, match="tylko gdy próbka jest wyłączona"):
        load_dataset(metadata, audio)
