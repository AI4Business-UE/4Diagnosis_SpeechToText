import json
from pydantic import BaseModel, Field
from typing import Optional


class Patient(BaseModel):
    first_name: Optional[str] = Field(
        default=None,
        description=(
            "Imię pacjenta. Ekstraktuj tylko wtedy, gdy zostalo jawnie podane w tekscie. "
            "Nie zgaduj imienia na podstawie innych danych."
        )
    )
    last_name: Optional[str] = Field(
        default=None,
        description=(
            "Nazwisko pacjenta. Ekstraktuj tylko wtedy, gdy zostalo jawnie podane w tekscie. "
            "Zmień formę tylko jeśli przypadek <> mianownik, ale bez dodatkowych slow typu 'pacjent'."
        )
    )
    pesel: Optional[str] = Field(
        default=None,
        description=(
            "Numer PESEL pacjenta. Zwracaj jako string zawierajacy same cyfry, bez spacji, myslnikow i kropek. "
            "PESEL ma zwykle 11 cyfr. Jesli numer nie jest podany, ustaw null."
        )
    )
    age: Optional[int] = Field(
        default=None,
        description=(
            "Wiek pacjenta jako liczba calkowita. Ekstraktuj tylko wtedy, gdy wiek został podany wprost, "
            "np. 'ma 54 lata', 'lat 54'. Nie wyliczaj wieku z PESEL-u."
        )
    )


class PatientExtraction(BaseModel):
    patient: Patient = Field(description="Dane pacjenta wyekstraktowane z tekstu.")


_schema = PatientExtraction.model_json_schema()

PATIENT_PROMPT = f"""
Jesteś asystentem medycznym specjalizującym się w ekstrakcji informacji z transkrypcji lekarza.

ZADANIE: Z podanego transkryptu wyekstraktuj dane pacjenta.

ZASADY:
1. Wyciągaj tylko informacje jawnie podane w tekście.
2. Jeśli wartość nie jest podana, użyj null.
3. Nie zgaduj imienia, nazwiska, wieku ani PESEL-u.
4. NIE WYLICZAJ WIEKU Z PESEL-u - Ekstraktuj wiek WYŁĄCZNIE jeśli pojawi się w treści transkrypcji.
5. PESEL zwróć jako tekst z samymi cyframi (11 cyfr). Jeśli PESEL nie jest pełny (nie ma 11 cyfr) to wstaw null. Jeśli PESEL pojawi się w formie cyfr odzielonych spacją lub w formie tekstu, to złącz go w jeden znakowy łańcuch cyfr. 
6. Ignoruj informacje o materiale, narządach, zmianach, wymiarach i kolorach.
7. Zwróć wyłącznie poprawny JSON zgodny ze schematem.
8. Imię i nazwisko zwróć w podstawowej nieodmienionej formie.

PRZYKŁADY POPRAWNEGO WNIOSKOWANIA:
Tekst: "Pacjentka Anna Nowak, PESEL 64072812345, lat 59. Fragment nerki z moczowodem."
Odpowiedź: {{"patient": {{"first_name": "Anna", "last_name": "Nowak", "pesel": "64072812345", "age": 59}}}}

Tekst: "Nerka o wymiarach 11x9x7 cm z moczowodem długości 1,5 cm oraz okoliczną tkanką tłuszczową."
Odpowiedź: {{"patient": {{"first_name": null, "last_name": null, "pesel": null, "age": null}}}}

Tekst: "Mamy pacjenta Tomasza Wiśniewskiego PESEL 6 4 0 siedem dwa osiem jeden dwa trzy cztery pięć lat 60."
Odpowiedź: {{"patient": {{"first_name": "Tomasz", "last_name": "Wiśniewski", "pesel": "64072812345", "age": 60}}}}

SCHEMAT JSON:
{json.dumps(_schema, ensure_ascii=False, indent=2)}
"""
