import json
from pydantic import BaseModel, Field
from typing import Optional, Literal


class Component(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description=(
            "Nazwa narządu, tkanki lub materiału, np. 'nerka', 'moczowód', "
            "'tkanka tłuszczowa', 'fragment skóry', 'bioptat', 'nadnercze', "
            "'pęcherzyk żółciowy', 'jajowód'. Podaj w mianowniku, małymi literami."
        )
    )
    count: Optional[int] = Field(
        default=None,
        description=(
            "Liczba sztuk / fragmentów tylko wtedy, gdy jest jawnie podana w tekście. "
            "Np. 'cztery bioptaty' -> 4, 'dwa fragmenty' -> 2. "
            "Jeśli liczba nie jest podana wprost, ustaw null."
        )
    )
    dim_x: Optional[float] = Field(default=None, description="Pierwszy wymiar (szerokość). Np. z '11x9x7 cm' → 11.0")
    dim_y: Optional[float] = Field(default=None, description="Drugi wymiar (wysokość/długość). Np. z '11x9x7 cm' → 9.0")
    dim_z: Optional[float] = Field(default=None, description="Trzeci wymiar (głębokość/grubość). Np. z '11x9x7 cm' → 7.0")
    length: Optional[float] = Field(
        default=None,
        description=(
            "Długość, jeśli podana osobno zamiast wymiarów xyz. "
            "Np. 'moczowód długości 5 cm' → 5.0. Jeśli podano xyz, to length = null."
        )
    )
    diameter: Optional[float] = Field(
        default=None,
        description=(
            "Średnica, jeśli podana zamiast wymiarów xyz. "
            "Np. 'znamię średnicy 0,5 cm' → 0.5. Jeśli podano xyz, to diameter = null."
        )
    )
    unit: Optional[Literal["cm", "mm"]] = Field(
        default=None,
        description=(
            "Jednostka wymiarów. Ustaw 'cm' lub 'mm' tylko wtedy, gdy wynika z tekstu. "
            "Jeśli komponent nie ma podanych wymiarów, ustaw null. Nie ustawiaj 'cm' domyślnie."
        )
    )
    description: Optional[str] = Field(
        default=None,
        description="Krótki opis dodatkowy z tekstu, np. 'wielotorbielowata', 'zmieniona zapalnie'. Pomijamy szczegóły zmian/guzów."
    )


class ComponentExtraction(BaseModel):
    components: list[Component] = Field(
        default_factory=list,
        description="Lista wszystkich komponentów (narządów/tkanek) wymienionych w opisie."
    )


_schema = ComponentExtraction.model_json_schema()

COMPONENT_PROMPT = f"""
Jesteś asystentem medycznym specjalizującym się w patomorfologii.

ZADANIE: Z podanego transkryptu mowy lekarza opisującego preparat makroskopowy
wyekstrahuj wszystkie KOMPONENTY — narządy, tkanki, fragmenty materiału —
wraz z ich wymiarami.

ABSOLUTNE ZASADY EKSTRAKCJI:
0. Wyciągaj WYŁĄCZNIE informacje jawnie podane w tekście. Jeśli wartość nie jest podana, ustaw null.
1. Jeden opis może zawierać WIELE komponentów (np. nerka + moczowód + tkanka tłuszczowa).
2. Wymiary podane jako "AxBxC cm" → dim_x=A, dim_y=B, dim_z=C.
3. Wymiary podane jako "długości X cm" → length=X (bez dim_x/y/z).
4. Wymiary podane jako "średnicy X cm" → diameter=X (bez dim_x/y/z).
5. "Milimetry" / "mm" → unit="mm". W przeciwnym razie unit="cm".
6. Słowne liczebniki przelicz na cyfry (np. "jedenaście" → 11).
7. GUZY i ZMIANY CHOROBOWE są ekstrahowane przez LESION_PROMPT — nie dodawaj ich tutaj jako Component.
8. Nie dodawaj informacji od siebie.
9. Pole count ustawiaj tylko wtedy, gdy liczba sztuk jest podana wprost.
10. Jeśli tekst wymienia kilka osobnych fragmentów z różnymi wymiarami, zwróć je jako osobne komponenty z count=null.
11. Nigdy nie ustawiaj count=1, jeśli liczebnik nie został podany wprost.
12. Nie traktuj jako komponentów: linii zszywek, tuszy, marginesów, odległości od marginesów.
13. Określenia jak "okoliczna", "drobny", "zmieniona zapalnie" wpisuj do description.
14. Każdy komponent musi mieć pole name.
15. Jeśli w tekście jest "fragment + narząd", wpisz to w całości do name (np. "fragment nerki").
16. Oznaczenia strony wpisuj do name (np. "nasieniowód lewy").

PRZYKŁADY POPRAWNEGO WNIOSKOWANIA:
Tekst: "Nerka o wymiarach 11x9x7 cm z moczowodem długości 1,5 cm oraz okoliczną tkanką tłuszczową. Na przekrojach obecny lity guz o wymiarach 10x8x6 cm."
Odpowiedź: {{"components": [{{"name": "nerka", "count": null, "dim_x": 11.0, "dim_y": 9.0, "dim_z": 7.0, "length": null, "diameter": null, "unit": "cm", "description": null}}, {{"name": "moczowód", "count": null, "dim_x": null, "dim_y": null, "dim_z": null, "length": 1.5, "diameter": null, "unit": "cm", "description": null}}, {{"name": "tkanka tłuszczowa", "count": null, "dim_x": null, "dim_y": null, "dim_z": null, "length": null, "diameter": null, "unit": null, "description": "okoliczna"}}]}}
(guz NIE jest komponentem — należy do LESION_PROMPT)

Tekst: "Cztery bioptaty o długości od 0,5 cm do 1,8 cm."
Odpowiedź: {{"components": [{{"name": "bioptat", "count": 4, "dim_x": null, "dim_y": null, "dim_z": null, "length": null, "diameter": null, "unit": "cm", "description": "długość od 0,5 do 1,8 cm"}}]}}

Odpowiedz WYŁĄCZNIE poprawnym JSONem zgodnym z tym schematem:
{json.dumps(_schema, indent=2, ensure_ascii=False)}
"""
