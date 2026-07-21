import json
from pydantic import BaseModel, Field
from typing import Optional, Literal, List


class Lesion(BaseModel):
    type: Optional[str] = Field(
        None, description="Typ zmiany patologicznej",
        examples=["guz", "torbiel", "polip", "ognisko", "zmiana"]
    )
    dim_x: Optional[float] = Field(None, description="Wymiar X (szerokość)", ge=0)
    dim_y: Optional[float] = Field(None, description="Wymiar Y (wysokość)", ge=0)
    dim_z: Optional[float] = Field(None, description="Wymiar Z (głębokość)", ge=0)
    diameter: Optional[float] = Field(None, description="Średnica", ge=0)
    length: Optional[float] = Field(None, description="Długość", ge=0)
    unit: str = Field("cm", description="Jednostka wymiarów, możliwe wartości: ['cm', 'mm']")
    color: Optional[str] = Field(None, description="Kolor zmiany")
    structure: Optional[str] = Field(
        None,
        description=(
            "'lity' gdy: lity/jednolity/solidny. "
            "'torbielowaty' gdy: torbielowaty/torbiel. "
            "'lito-torbielowaty' gdy: lito-torbielowaty lub częściowo lity częściowo torbielowaty. "
            "Null gdy nie podano LUB gdy opis dotyczy konsystencji (wtedy do additional_notes)."
        ),
        examples=["lity", "torbielowaty", "lito-torbielowaty"]
    )
    features: List[str] = Field(
        default_factory=list, description="Cechy dodatkowe zmiany",
        examples=["martwica", "wylewy_krwawe", "zwapnienia", "owrzodzenie"]
    )
    infiltration: Optional[str] = Field(None, description="Stopień naciekania tkanek",
                                        examples=["brak", "do_miazszu", "nacieka_tkanke_tluszczowa", "nacieka_sciane", "poza_narzad"])
    location_description: Optional[str] = Field(None, description="Dokładna lokalizacja zmiany")
    organ: Optional[str] = Field(None, description="Narząd w mianowniku, małymi literami")
    shape: Optional[str] = Field(
        None, description="Kształt zmiany",
        examples=["okrągła", "owalna", "nieregularna", "gwiaździsta", "lobularna"]
    )
    borders: Optional[str] = Field(
        None, description="Granice zmiany",
        examples=["ostre", "zatarte", "nieregularne", "regularne"]
    )
    additional_notes: Optional[str] = Field(None, description="Dodatkowe uwagi, w tym konsystencja/tekstura")
    component_index: Optional[int] = Field(
        None,
        description=(
            "Indeks (0-bazowy) komponentu z listy 'components', w którym znajduje się ta zmiana. "
            "Ustaw TYLKO gdy tekst JEDNOZNACZNIE wskazuje, że zmiana należy do konkretnego komponentu. "
            "Ustaw null gdy powiązanie jest niejasne lub nie podano komponentów."
        )
    )


class LesionExtraction(BaseModel):
    lesions: List[Lesion] = Field(
        default_factory=list,
        description="Lista wykrytych zmian patologicznych (guzów, torbieli, polipów, ognisk)"
    )


_schema = LesionExtraction.model_json_schema()

_LESION_RULES = """
ABSOLUTNE ZASADY EKSTRAKCJI:
0. ZERO HALUCYNACJI: Operuj WYŁĄCZNIE na informacjach zawartych w tekście. Jeśli atrybut
   nie pojawia się w tekście, przypisz null.
1. Jeden opis może zawierać WIELE zmian (np. kilka polipów, kilka ognisk).
2. Wymiary podane jako "AxBxC cm" → dim_x=A, dim_y=B, dim_z=C.
3. Wymiary podane jako "średnicy X cm" → diameter=X (bez dim_x/y/z).
4. Wymiary podane jako "długości X cm" → length=X (bez dim_x/y/z).
5. "Milimetry" / "mm" → unit="mm". W przeciwnym razie unit="cm".
6. Słowne liczebniki przelicz na cyfry (np. "trzy przecinek dwa" → 3.2).
7. NIE wyciągaj narządów/tkanek — to robi moduł ComponentExtraction.
8. Rozpoznawaj synonimy: "martwica" = "nekroza", "wylewy_krwawe" = "krwawienie".
9. Jeśli lekarz się poprawia, bierz poprawioną wartość.
10. W polu organ podaj nazwę w mianowniku, małymi literami.
11. Granice (borders): "gładki"/"dobrze odgraniczony" → "ostre"; "nieregularny" → "nieregularne"; "rozmyty"/"zatarty" → "zatarte".
12. Infiltration: "ograniczony do miąższu" → "do_miazszu"; "naciekający tk. tłuszczową" → "nacieka_tkanke_tluszczowa"; "naciekający pełną grubość ściany" → "nacieka_sciane"; "naciekający poza narząd" → "poza_narzad"; brak wzmianki → null.
13. Shape: "okrągły" → "okrągła"; "owalny" → "owalna"; "guzkowaty"/"bulwiasty" → "lobularna"; "gwiazdkowaty" → "gwiaździsta"; "nieregularny" → "nieregularna".
14. Structure: TYLKO "lity"/"torbielowaty"/"lito-torbielowaty" lub null. Konsystencja/tekstura (miękki, galaretowaty) → additional_notes.
15. Odporność na szum ASR: ignoruj brak interpunkcji i błędy ortograficzne.

PRZYKŁADY:
Tekst: "Nerka o wymiarach 11x9x7 cm. Na przekrojach w obrębie miąższu nerki obecny lity guz o wymiarach 10x8x6 cm barwy beżowej z wylewami krwawymi i centralną martwicą."
Odpowiedź: {{"lesions": [{{"type": "guz", "dim_x": 10.0, "dim_y": 8.0, "dim_z": 6.0, "diameter": null, "unit": "cm", "color": "beżowej", "structure": "lity", "features": ["martwica", "wylewy_krwawe"], "infiltration": null, "location_description": "w obrębie miąższu nerki", "organ": "nerka", "shape": null, "borders": null, "additional_notes": null}}]}}

Tekst: "Bioptat nerki o łącznej długości 1,5 cm."
Odpowiedź: {{"lesions": []}}
"""

LESION_SPLIT_PROMPT = f"""
Jesteś asystentem medycznym specjalizującym się w patomorfologii i opisach makroskopowych.

ZADANIE: Z podanego transkryptu mowy lekarza opisującego preparat makroskopowy
wyekstrahuj wszystkie ZMIANY PATOLOGICZNE (guzy, torbiele, polipy, ogniska).
Jeśli tekst NIE opisuje żadnej zmiany patologicznej, zwróć {{"lesions": []}}.

{_LESION_RULES}

Odpowiedz WYŁĄCZNIE poprawnym JSONem zgodnym z tym schematem:
{json.dumps(_schema, indent=2, ensure_ascii=False)}
"""

# %s zostanie zastąpiony przez JSON z nazwami komponentów (np. '["nerka", "moczowód"]')
LESION_CHAINED_PROMPT = f"""
Jesteś asystentem medycznym specjalizującym się w patomorfologii i opisach makroskopowych.

ZADANIE: Z podanego transkryptu mowy lekarza opisującego preparat makroskopowy
wyekstrahuj wszystkie ZMIANY PATOLOGICZNE (guzy, torbiele, polipy, ogniska).
Jeśli tekst NIE opisuje żadnej zmiany patologicznej, zwróć {{"lesions": []}}.

{_LESION_RULES}

DODATKOWA ZASADA — RELACJA LESION ↔ COMPONENT:
Dostajesz nazwy KOMPONENTÓW BADANIA wyekstraktowanych wcześniej z tej samej transkrypcji.
Po wydobyciu zmian patologicznych przyporządkuj im pole component_index (indeks 0-bazowy)
TYLKO jeżeli jednoznacznie wynika to z transkrypcji. W przeciwnym razie ustaw null.

KOMPONENTY BADANIA:
%s

Odpowiedz WYŁĄCZNIE poprawnym JSONem zgodnym z tym schematem:
{json.dumps(_schema, indent=2, ensure_ascii=False)}
"""
