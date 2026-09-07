# Data sanity check

`data_sanity_check` to końcowy guardrail dla formularza zbudowanego przez pipeline.
Nie diagnozuje pacjenta i nie zastępuje walidacji medycznej. Jego zadanie jest prostsze:
wyłapać techniczne albo logiczne problemy w danych, zanim potraktujemy formularz jako sensowny wynik.

Główny kontrakt:

```python
run_data_sanity_check(transcript, form_data, mode="rules", repair_scope="all") -> sanity_result
```

## Gdzie jest używany

- `Pipeline.run()` odpala sanity po STT, NER, RAG/answerer i zbudowaniu `form_data`.
- Runtime WebSocket zapisuje skrócony wynik do lokalnego JSONL jako hidden QA log.
- Lokalny eval używa go do porównywania trybów sanity i kalibracji reguł.

Domyślny runtime aplikacji używa `mode="rules"`, czyli bez LLM i bez sieci.
Frontend nie dostaje warningów sanity jako osobnego pola.

## Wejście i wyjście

Wejście:

- `transcript` - tekst po transkrypcji/korekcji, używany do kontroli zgodności.
- `form_data` - formularz z polami `name`, `organ`, `age`, `pesel`, `description`.
- `mode` - tryb działania sanity.
- `repair_scope` - zakres naprawy używany tylko w trybie `review_and_repair`.

Wynik `sanity_result` zawiera:

- `status` - `ok`, `warning` albo `critical`.
- `score` - heurystyczny ranking jakości od `0` do `1`.
- `issues` - lista znalezionych problemów.
- `metrics` - krótkie metryki, np. długość transkryptu i opisu.
- `llm_review` - metadane LLM review.
- `repair` - metadane i wynik ewentualnej naprawy.

## Tryby

`rules` to domyślny tryb. Działa deterministycznie, nie używa LLM, nie wykonuje requestów
i nie wymaga kluczy API.

`rules_and_llm` najpierw odpala reguły, a potem opcjonalny LLM review. LLM może dodać własne
issue, ale nie poprawia formularza.

`review_and_repair` to eksperymentalny tryb opt-in. Odpala LLM repair w wybranym zakresie,
waliduje zaproponowane zmiany i ponownie liczy reguły na naprawionym formularzu. Samo istnienie
tego trybu nie zmienia runtime aplikacji. Formularz w pipeline jest podmieniany tylko wtedy, gdy
konfiguracja jawnie ustawi `apply_sanity_repair=True`.

## Reguły (tryb rules)

Reguły sprawdzają:

- wymagane pola: `organ`, `name`, `age`, `pesel`, `description`;
- jakość opisu, czyli czy opis nie jest tylko znakiem, liczbą albo pustą treścią;
- PESEL: długość, format, checksumę i datę;
- wiek oraz zgodność wieku z datą urodzenia z PESEL;
- wymiary w opisie i transkrypcie;
- limity wymiarów per narząd z `organ_plausibility.py`;
- zgodność transkryptu z opisem, np. czy transcript mówi o zmianie, której opis nie zawiera.

Reguły są celowo proste i konserwatywne. Mają łapać oczywiste nonsensy, a nie oceniać poprawność
medyczną preparatu.

## Kody issue

Najważniejsze kody:

- `missing_required_field` - brakuje wymaganego pola formularza.
- `description_not_meaningful` - opis istnieje, ale nie ma sensownej treści.
- `invalid_pesel_length` - PESEL nie ma 11 znaków.
- `invalid_pesel_format` - PESEL zawiera coś poza cyframi.
- `invalid_pesel_checksum` - suma kontrolna PESEL się nie zgadza.
- `invalid_pesel_date` - PESEL koduje niemożliwą albo przyszłą datę.
- `age_not_a_number` - wiek nie jest liczbą.
- `negative_age` - wiek jest ujemny.
- `age_too_high` - wiek jest powyżej rozsądnego zakresu.
- `age_pesel_mismatch` - wiek nie pasuje do daty z PESEL.
- `non_positive_dimension` - wymiar jest zerowy albo ujemny.
- `suspicious_unit_meter` - w opisie tkankowym pojawiły się metry.
- `suspicious_large_dimension` - wymiar przekracza globalny limit dla nieznanego narządu.
- `implausible_dimension_for_organ` - wymiar przekracza limit dla rozpoznanego narządu.
- `lesion_without_dimension` - opis mówi o zmianie, ale bez wymiaru.
- `possible_lesion_omitted` - transcript mówi o zmianie, ale opis może ją pomijać.

Każde issue ma przynajmniej `severity`, `source`, `code`, `field` i `message`.

## Scoring i status

`status` jest prosty:

- brak issue -> `ok`;
- dowolne issue z `severity="error"` -> `critical`;
- pozostałe issue -> `warning`.

`score` jest heurystycznym rankingiem jakości, a nie decyzją kliniczną. Każdy kod issue ma wagę,
a wynik jest liczony multiplikatywnie. Dzięki temu kilka lekkich warningów obniża score stopniowo,
a twardy błąd, np. `0 cm`, obniża go mocniej.

W evalu główne kryteria poprawności guardraila to `expected_flag` oraz
`expected_issue_codes_covered`. Pierwsze mówi, czy sanity miało w ogóle coś zgłosić. Drugie mówi,
czy wykryło oczekiwane typy problemów. `expected_severity` służy do kalibracji wag i progów. Jeśli
`expected_flag` i `expected_issue_codes_covered` są trafione, ale `expected_severity` się rozjeżdża,
to zwykle znaczy, że trzeba świadomie dostroić scoring, a nie że guardrail nie wykrył problemu.

## LLM review i repair

`repair_scope` działa tylko dla `review_and_repair`:

- `patient_data` - LLM może poprawiać `name`, `age`, `pesel`;
- `description` - LLM może poprawiać `organ`, `description`;
- `all` - LLM może poprawiać wszystkie pola formularza.

Kod nadal waliduje wynik LLM:

- odrzuca zmiany poza zakresem;
- nie przepuszcza nieznanych pól formularza;
- PESEL może się zmienić tylko wtedy, gdy pełny numer występuje jawnie w transkrypcie;
- wiek musi być pusty albo liczbą w rozsądnym zakresie.

Repair nie powinien dodawać faktów spoza transkryptu. Jeśli LLM nie jest pewny, powinien zostawić
pole bez zmian.

## Eval sanity

Do samego guardraila używamy `backend/eval/data/sanity_guardrail_eval_gold.jsonl`. Ten plik ma
gotowe `transcript` i `form_data`, więc nie testuje Whispera, NER, RAG ani answerera. Służy do
sprawdzania, czy sanity wykrywa właściwe problemy i czy scoring ma sens. To powinien być wspólny
gold set dla zespołu, jeśli chcemy porównywać wyniki na tych samych przykładach.

Do pełnego flow audio używamy `backend/eval/data/metadata/samples_metadata.xlsx`. Ten eval odpala
pipeline od audio do formularza, a potem liczy wybrane tryby sanity na tym samym wyniku.

To zbiór testowy z fikcyjnymi PESEL-ami (kolumna `synthetic`), więc eval automatycznie wycisza
w raporcie issue PESEL/wieku dla tych próbek — inaczej fałszywy PESEL zalewałby wynik szumem.
Wyciszanie dotyczy tylko raportu evala; sam `data_sanity_check` działa bez zmian.

Pełna instrukcja uruchamiania evala jest w `backend/eval/EVAL.md`.

## Jak uruchomić lokalnie

Szybki test reguł (bez LLM), przez pytest:

```bash
cd backend && python3 -m pytest src/app_stt/tests/test_data_sanity.py -q
```

Pełny workflow evala, w tym offline eval na `sanity_guardrail_eval_gold.jsonl`, jest opisany w
`backend/eval/EVAL.md`.
