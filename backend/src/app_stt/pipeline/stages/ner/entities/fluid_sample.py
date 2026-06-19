import json
from pydantic import BaseModel, Field
from typing import Optional, Literal


class FluidSample(BaseModel):
    source: Optional[str] = Field(
        default=None,
        description=(
            "Pochodzenie anatomiczne płynu. Ekstraktuj dosłownie z tekstu "
            "(np. 'jama opłucnowa', 'osierdzie', 'torbiel'). Nie zamieniaj nazw potocznych na medyczne synonimy."
        )
    )
    material_type: Optional[str] = Field(
        default=None,
        description=(
            "Rodzaj materiału, płynu lub procedura pobrania (np. 'mocz', 'popłuczyny', 'BAL', 'BAC', 'LBC', 'PMR'). "
            "Jeśli tekst łączy typ z lokalizacją (np. 'BAL z płata środkowego'), rozdziel: typ → material_type, lokalizacja → source."
        )
    )
    volume_ml: Optional[float] = Field(
        default=None,
        description="Objętość nadesłanego płynu w mililitrach (ml). Jeśli podano w litrach (np. 0,5 l), przelicz na ml (500)."
    )
    color: Optional[str] = Field(
        default=None,
        description="Kolor lub zabarwienie płynu. Zachowaj formę gramatyczną z tekstu (np. 'zielonawego', 'krwista')."
    )
    clarity: Optional[Literal["klarowny", "mętny"]] = Field(
        default=None,
        description="'klarowny' gdy: klarowny/przejrzysty/brak mętności. 'mętny' gdy: mętny/zmętniały."
    )
    consistency: Optional[str] = Field(
        default=None,
        description="Konsystencja i charakter płynu (np. 'ropny', 'gęsty', 'śluzowy')."
    )
    fixation: Optional[str] = Field(
        default=None,
        description="Sposób utrwalenia płynu (np. 'nieutrwalony z heparyną'). Ignoruj szczegółowe dawki/proporcje."
    )


class FluidSampleExtraction(BaseModel):
    fluid_samples: list[FluidSample] = Field(
        default_factory=list,
        description="Lista wszystkich płynów wymienionych w opisie."
    )


_schema = FluidSampleExtraction.model_json_schema()

FLUID_SAMPLE_PROMPT = f"""
Jesteś zaawansowanym systemem ekstrakcji informacji medycznych (NER), wyspecjalizowanym
w patomorfologii i cytologii złuszczeniowej.

ZADANIE: Z podanego transkryptu wyekstrahuj próbki płynów i materiały cytologiczne.
Jeśli tekst NIE opisuje próbki płynu, zwróć {{"fluid_samples": []}}.

ABSOLUTNE ZASADY EKSTRAKCJI:
1. ZERO HALUCYNACJI: Operuj WYŁĄCZNIE na informacjach zawartych w tekście. Jeśli atrybut nie pojawia się w tekście, przypisz null.
2. EKSTRAKCJA DOSŁOWNA: W polach tekstowych używaj dokładnie takich samych słów i form gramatycznych jak w tekście.
3. ROZDZIELANIE MATERIAŁU OD ŹRÓDŁA: "BAL z płata środkowego" → material_type="BAL", source="z płata środkowego".
4. OBSŁUGA NEGACJI: "brak mętności" / "nie stwierdzono zmętnienia" → clarity="klarowny".
5. STANDARYZACJA JEDNOSTEK: volume_ml w mililitrach. Litry przelicz na ml (0,2 l → 200). "cc" = ml.
6. ODPORNOŚĆ NA SZUM ASR: Ignoruj brak interpunkcji i błędy ortograficzne.
7. IGNOROWANIE DAWEK: W polu fixation ignoruj szczegółowe proporcje utrwalaczy.

PRZYKŁADY POPRAWNEGO WNIOSKOWANIA:
Tekst: "Zaaspirowano 1,2 litra płynu z jamy otrzewnowej. Materiał gęsty, krwisty. Nie stwierdzono zmętnienia. Zabezpieczono w formalinie."
Odpowiedź: {{"fluid_samples": [{{"source": "z jamy otrzewnowej", "material_type": "płynu", "volume_ml": 1200.0, "color": "krwisty", "clarity": "klarowny", "consistency": "gęsty", "fixation": "w formalinie"}}]}}

Tekst: "BAL z płata środkowego, 20 ml. Mętny."
Odpowiedź: {{"fluid_samples": [{{"source": "z płata środkowego", "material_type": "BAL", "volume_ml": 20.0, "color": null, "clarity": "mętny", "consistency": null, "fixation": null}}]}}

Tekst: "Mocz z drugiej mikcji. Przejrzysty."
Odpowiedź: {{"fluid_samples": [{{"source": "z drugiej mikcji", "material_type": "Mocz", "volume_ml": null, "color": null, "clarity": "klarowny", "consistency": null, "fixation": null}}]}}

Tekst: "Nerka o wymiarach 11x9x7 cm z moczowodem długości 1,5 cm."
Odpowiedź: {{"fluid_samples": []}}

Odpowiedz WYŁĄCZNIE poprawnym JSONem zgodnym z tym schematem:
{json.dumps(_schema, indent=2, ensure_ascii=False)}
"""
