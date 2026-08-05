from datetime import datetime

from app_stt.services.utils import extract_organs, extract_patient_data


def _calculate_age_from_pesel(pesel: str) -> int | None:
    if not pesel or len(pesel) != 11 or not pesel.isdigit():
        return None

    try:
        year = int(pesel[0:2])
        month = int(pesel[2:4])
        day = int(pesel[4:6])

        if 1 <= month <= 12:
            century = 1900
        elif 21 <= month <= 32:
            century = 2000
            month -= 20
        else:
            return None

        birth_date = datetime(century + year, month, day)
        today = datetime.today()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
    except (ValueError, IndexError):
        return None


def build_form_data_from_entities(
    entities: dict,
    corrected_text: str,
    patient_metadata: dict | None = None,
) -> dict[str, str]:
    patient_metadata = patient_metadata or {}
    patient_data = extract_patient_data(entities)
    organs = extract_organs(entities)

    full_name = (
        f"{patient_data['first_name']} {patient_data['last_name']}"
        if patient_data["first_name"] and patient_data["last_name"]
        else ""
    )
    if not full_name and patient_metadata.get("name"):
        full_name = patient_metadata.get("name", "")

    calculated_age = (
        patient_data["age"] or _calculate_age_from_pesel(patient_data["pesel"])
    )
    if calculated_age is None and patient_metadata.get("age"):
        calculated_age = patient_metadata.get("age", "")

    return {
        "name": full_name or patient_metadata.get("name", ""),
        "organ": organs,
        "age": str(calculated_age) if calculated_age is not None else patient_metadata.get("age", ""),
        "pesel": patient_data["pesel"] or patient_metadata.get("pesel", ""),
        "description": corrected_text,
    }
