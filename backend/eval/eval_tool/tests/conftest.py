import json

import pytest
from openpyxl import Workbook


@pytest.fixture
def write_metadata():
    def write(path, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["id", "format", "nazwa pliku", "tekst referencyjny"])
        for row in rows:
            sheet.append(row)
        workbook.save(path)

    return write


@pytest.fixture
def complete_reference():
    return {
        "reviewed": True,
        "entities": {
            "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
            "components": [],
            "lesions": [],
            "fluid_samples": [],
        },
    }


@pytest.fixture
def write_references():
    def write(path, samples):
        path.write_text(
            json.dumps({"version": 1, "samples": samples}),
            encoding="utf-8",
        )

    return write
