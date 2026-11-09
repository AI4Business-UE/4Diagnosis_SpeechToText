import pytest
from openpyxl import Workbook

DEFAULT_METADATA_HEADERS = ["id", "format", "nazwa pliku", "tekst referencyjny"]


@pytest.fixture
def write_metadata():
    def write(path, rows, headers=None):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers or DEFAULT_METADATA_HEADERS)
        for row in rows:
            sheet.append(row)
        workbook.save(path)

    return write
