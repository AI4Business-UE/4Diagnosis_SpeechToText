# Ewaluacja pipeline'u

Ten plik opisuje lokalny eval dla projektu 4Diagnosis SpeechToText: skąd bierzemy dane, jak odpalić STT/NER/end-to-end/sanity eval i jak czytać metryki.

## Dane

Dane źródłowe są trzymane poza repozytorium: [folder Google Drive](https://drive.google.com/drive/folders/1J5VXlJVQQC9Qi66E2UWqxaaoEeCy17uU).

Audio kopiujemy lokalnie do:

```text
backend/eval/data/stt/audio_samples
```

Pliki audio są ignorowane przez Git.

Metadata można skopiować lokalnie do:

```text
backend/eval/data/stt/metadata/samples_metadata.xlsx
```

Metadata też są ignorowane przez Git.

## Flow ewaluacji

1. Skopiować lokalnie audio i `samples_metadata.xlsx`.
2. Zbudować roboczą listę próbek na podstawie metadanych.
3. Odpalić aktualny pipeline STT na wybranych modelach i konfiguracjach preprocessingu.
4. Porównać transkrypcje modelu z referencją.
5. Zapisać surowe wyniki do CSV.
6. Wygenerować krótkie podsumowanie per `model + preprocessing`.

Robocza lista próbek zapisuje się tutaj:

```text
backend/eval/results/stt_manifest.csv
```

Ten plik jest ignorowany przez Git.

Wyniki evala zapisują się tutaj:

```text
backend/eval/results/stt_eval_results.csv
backend/eval/results/stt_eval_summary.csv
```

Przetworzone audio z preprocessingu zapisuje się lokalnie w:

```text
backend/eval/results/preprocessed_audio
```

Ten folder jest roboczy i nie powinien iść do commita.

## Zbiory evalowe

W repo są trzy typy danych evalowych:

- `backend/eval/baselines/stt/` - wcześniejsze wyniki/baseline dla Whispera. Te pliki służą do porównania nowych wyników z tym, co było już policzone wcześniej.
- `backend/eval/data/ner/ner_eval_samples.jsonl` - mały syntetyczny gold set do NER evala. Każdy wiersz ma `transcript` i `expected_entities`.
- `backend/eval/data/end_to_end/end_to_end_eval_samples.csv` - mały syntetyczny gold set do end-to-end evala na audio. Każdy wiersz ma `audio_path`, `ref_transcript` i `expected_entities`, więc można policzyć zarówno metryki STT, jak i NER.

`expected_entities` to ręcznie przygotowany JSON z oczekiwanymi encjami, np. `patient`, `components`, `lesions`, `fluid_samples`. Dzięki temu eval nie sprawdza tylko, czy pipeline coś zwrócił, ale też czy zwrócił właściwe dane.

## Definicje metryk

### STT

- `WER` (`Word Error Rate`) - błąd na poziomie słów, liczony **z ujednoliceniem zapisu liczb** (`5,5` = `5.5`, a `3,5 x 3,0 x 3,5` to jeden token). Im niżej, tym lepiej. `0.0` oznacza brak błędów.
- `CER` (`Character Error Rate`) - błąd na poziomie znaków, również z ujednoliceniem liczb. Im niżej, tym lepiej.
- `wer_strict` / `cer_strict` - te same metryki, ale **bez ujednolicenia zapisu liczb** — karzą różnicę formatu (`5,5` vs `5.5`). Porównanie z `WER`/`CER` pokazuje, ile błędu bierze się z samego zapisu, a ile z realnego przekręcenia słów.
- `number_recall` - ile liczb z referencji model przepisał poprawnie. Im bliżej `1.0`, tym lepiej.
- `number_precision` - ile liczb z transkrypcji ma pokrycie w referencji. Niskie precision = model **dodał** liczby, których nie było (halucynacja); recall tego nie łapie.
- `dimension_recall` - ile wymiarów z referencji model przepisał poprawnie, np. `1,5 cm` albo `3 x 2 cm`. Im bliżej `1.0`, tym lepiej.
- `dimension_precision` - ile wymiarów z transkrypcji ma pokrycie w referencji (analogicznie: wychwytuje dodane wymiary).
- `medical_term_recall` - ile terminów medycznych ze słownika projektu, obecnych w referencji, pojawiło się też w transkrypcji. Im bliżej `1.0`, tym lepiej.
- `pesel_accuracy` - dokładność PESEL-u, jeśli PESEL występuje w referencji. `1.0` oznacza idealne dopasowanie, `0.0` błąd, a pusta wartość oznacza brak PESEL-u w referencji.
- `has_critical_error` - czy próbka ma **twardy** błąd krytyczny: w liczbach, wymiarach albo PESEL-u (kategorie exact-match, wysokiej stawki). Terminologia medyczna jest liczona osobno (patrz `has_term_error`).
- `critical_error_count` - liczba twardych kategorii krytycznych (liczby / wymiary / PESEL) z błędem dla jednej próbki.
- `has_spurious_number` - czy próbka ma **dodaną** (halucynowaną) liczbę: `number_precision < 1.0`. Kategoria miękka, osobno od `has_critical_error`, który liczy zgubione wartości.
- `has_term_error` - czy próbka zgubiła jakiś termin medyczny obecny w referencji (kategoria miękka, śledzona osobno od błędów twardych).
- `duration_seconds` - całkowity czas przetwarzania jednej próbki.
- `audio_duration_seconds` - długość pliku audio.
- `real_time_factor` - stosunek czasu przetwarzania do długości audio. `3.0` oznacza, że przetwarzanie trwało 3 razy dłużej niż samo audio.
- `errors_count` - liczba próbek, które zakończyły się błędem technicznym dla danej konfiguracji.

### NER

- `precision` - ile danych wyciągniętych przez NER było poprawnych. Niskie precision oznacza dużo halucynowanych albo nadmiarowych encji.
- `recall` - ile oczekiwanych danych NER faktycznie znalazł. Niskie recall oznacza pominięcia.
- `f1` - średnia harmoniczna precision i recall; przydatna jako jedna liczba porównawcza.
- `tp` / `fp` / `fn` - liczba trafień, fałszywych trafień i pominięć.
- Metryki są liczone osobno dla `patient`, `components`, `lesions`, `fluid_samples` oraz jako `overall`.

### Sanity check

> **Uwaga o charakterze tego evala.** W trybie `jsonl`/`baseline_csv` formularz jest
> **syntetyczną rekonstrukcją** z gold-encji NER (`build_form_data`), a nie realnym fillem LLM.
> Nie ma tu etykiety „czy formularz faktycznie jest problematyczny", więc eval nie produkuje
> metryki jakościowej — to harness do przeglądu i porównania (co łapią reguły vs LLM), nie
> zescorowany eval. Kolumny `manual_*` są puste, do ręcznej anotacji. Zbiór jest mały.
> Realne fille ocenia dopiero tryb `audio_manifest` (audio -> STT -> NER -> sanity check).

- `status` - trójpoziomowy, wyprowadzony z severity: `ok` (brak issues), `warning` (są issues,
  ale bez błędów krytycznych), `critical` (co najmniej jeden issue o severity `error`).
- `score` - wynik jakości w `(0, 1]`, liczony multiplikatywnie (każde issue mnoży przez `1 - waga`,
  wagi per kod issue). Nie zeruje się od kilku drobnych warningów; błąd krytyczny ciągnie mocniej.
- `issue_count` - liczba wszystkich issues.
- `issue_codes` - kody wykrytych problemów, np. `missing_required_field`, `invalid_pesel_checksum`, `suspicious_large_dimension`, `implausible_dimension_for_organ`.
- `issue_fields` / `missing_fields` - pola, których dotyczą issues; `field` rozróżnia teraz
  `description` od `transcript` (skąd pochodzi wykryty wymiar).
- `rules_issue_count` / `llm_issue_count` - rozdzielenie problemów wykrytych przez reguły i przez LLM-review.
- `llm_ran` / `llm_reason` - czy LLM-review realnie się wykonał i dlaczego nie
  (`disabled`, `no_api_key`, `http_error`, `parse_error`, `exception`, `ok`). Bez tego tryb z LLM
  bez klucza wyglądałby jak sam `rules`.
- `gold_has_patient` / `filtered_synthetic_issues` - w rekonstrukcji bez pacjenta braki
  name/age/pesel to artefakt (gold nie miał pacjenta), więc są odfiltrowane i tylko zliczone tutaj,
  żeby nie zawyżały `issue_count`.

LLM-review domyślnie odpala się tylko, gdy reguły coś znalazły (oszczędność kosztu). Żeby wymusić
LLM także na formularzach czystych wg reguł, ustaw `SANITY_LLM_FORCE=1`. Model LLM bierze się z
`SANITY_LLM_MODEL` (domyślnie `gpt-4o-2024-05-13`); tryby z LLM wymagają `OPENROUTER_API_KEY`/`OPENAI_KEY`.

**Zakresy sensowności per narząd.** Wymiary z opisu są porównywane z górną granicą sensownego
rozmiaru danego narządu (`backend/src/app_stt/data/organ_plausibility.py`). Narząd jest rozpoznawany
z pola `organ` (obsługa polskiej fleksji), a przekroczenie limitu daje `implausible_dimension_for_organ`;
dla nieznanego narządu obowiązuje globalny próg (`suspicious_large_dimension`, 50 cm). Wartości
zakresów są **wstępne** (TODO: przegląd przez osobę medyczną) i celowo hojne, żeby łapać tylko
wyraźny nonsens (np. 40 cm nerka), a nie preparaty powiększone patologicznie.

**Test na gotowych formularzach.** Tryb `--input-format form_jsonl` uruchamia sanity check na
gotowym `form_data` (bez rekonstrukcji z encji) — to realniejszy test niż `jsonl` i miejsce na
przyszłe zanonimizowane realne formularze. Curated fixture z przypadkami plausible/implausible jest
w `backend/eval/data/sanity/plausibility_fixture.jsonl`; każdy wiersz ma `expected_flag`/`note`,
które trafiają do wyniku, żeby ręcznie porównać `status` z oczekiwaniem.

## Komendy

Eval najlepiej odpalać przez backendowy venv:

```bash
backend/venv/bin/python backend/eval/stt/build_manifest.py
```

Jeśli eval odpala NER przez LLM, najpierw trzeba świadomie wczytać lokalny env:

```bash
set -a
source backend/env
set +a
```

Bez tego NER może przejść fallbackiem i wynik będzie tylko technicznym smoke testem, a nie realną oceną jakości NER.

Mały smoke eval:

```bash
backend/venv/bin/python backend/eval/stt/run_eval.py \
  --limit 1 \
  --models whisper-small \
  --preprocessing baseline
```

Większy run na wybranych modelach i konfiguracjach:

```bash
backend/venv/bin/python backend/eval/stt/run_eval.py \
  --models whisper-small whisper-medical-pl \
  --preprocessing baseline vad noise_reduction
```

Podsumowanie wyników:

```bash
backend/venv/bin/python backend/eval/stt/summarize_results.py \
  --input backend/eval/results/stt_eval_results.csv \
  --output backend/eval/results/stt_eval_summary.csv
```

Porównanie aktualnego runu z baseline:

```bash
backend/venv/bin/python backend/eval/stt/compare_baseline.py \
  --current backend/eval/results/stt_eval_results.csv \
  --baseline backend/eval/baselines/stt/whisper_comparison_results.csv \
  --output backend/eval/results/stt_baseline_comparison.csv
```

NER eval na referencyjnych transkryptach:

```bash
backend/venv/bin/python backend/eval/ner/run_eval.py \
  --input backend/eval/data/ner/ner_eval_samples.jsonl \
  --strategies chained split \
  --output backend/eval/results/ner_eval_results.csv
```

Podsumowanie NER:

```bash
backend/venv/bin/python backend/eval/ner/summarize_results.py \
  --input backend/eval/results/ner_eval_results.csv \
  --output backend/eval/results/ner_eval_summary.csv
```

End-to-end eval, czyli audio -> STT -> NER, odpalać tylko na małym limicie:

```bash
backend/venv/bin/python backend/eval/end_to_end/run_eval.py \
  --input backend/eval/data/end_to_end/end_to_end_eval_samples.csv \
  --limit 5 \
  --models whisper-small \
  --preprocessing baseline \
  --ner-strategies chained \
  --output backend/eval/results/end_to_end_eval_results.csv
```

Jeśli użyjemy `backend/eval/results/stt_manifest.csv` jako inputu, policzą się metryki STT, ale metryki NER nie pojawią się, dopóki manifest nie ma kolumny `expected_entities`.

Sanity eval na lokalnych plikach audio, czyli audio -> STT -> NER -> sanity check, też odpalać najpierw na małym limicie:

```bash
backend/venv/bin/python backend/eval/sanity/run_eval.py \
  --input backend/eval/results/stt_manifest.csv \
  --input-format audio_manifest \
  --limit 1 \
  --models whisper-small \
  --preprocessing baseline \
  --ner-strategies chained \
  --mode rules \
  --output backend/eval/results/sanity_eval_audio_results.csv
```

Porównanie wariantów `rules` / `rules_and_llm` / `llm_only` na tych samych danych daje `--mode all`,
a podsumowanie per tryb (rozkład statusów, średni score, ile dokłada LLM) liczy `summarize_results.py`:

```bash
backend/venv/bin/python backend/eval/sanity/run_eval.py \
  --input backend/eval/data/ner/ner_eval_samples.jsonl \
  --mode all \
  --output backend/eval/results/sanity_eval_results.csv

backend/venv/bin/python backend/eval/sanity/summarize_results.py \
  --input backend/eval/results/sanity_eval_results.csv \
  --output backend/eval/results/sanity_eval_summary.csv
```

Test zakresów sensowności na curated fixture (gotowe formularze, bez modeli i sieci):

```bash
backend/venv/bin/python backend/eval/sanity/run_eval.py \
  --input backend/eval/data/sanity/plausibility_fixture.jsonl \
  --input-format form_jsonl \
  --mode rules \
  --output backend/eval/results/sanity_plausibility_results.csv
```

W wyniku porównaj kolumnę `status` (flaguje = nie `ok`) z `expected_flag` — rozjazdy to false-positive/negative.

Prosty raport markdown z dostępnych wyników:

```bash
backend/venv/bin/python backend/eval/reporting/generate_report.py \
  --output backend/eval/results/eval_report.md
```

## Co commitować

Można commitować:

- kod evala,
- dokumentację,
- baseline CSV,
- syntetyczne gold sety (`ner_eval_samples.jsonl`, `end_to_end_eval_samples.csv`),
- świadomie wybrane wyniki CSV, jeśli nie zawierają danych wrażliwych.

Nie commitować:

- audio,
- metadanych lokalnych,
- `backend/env`,
- `stt_manifest.csv`,
- `preprocessed_audio`,
- roboczych wyników CSV z `backend/eval/results`, jeśli są tylko lokalnym outputem runu.
