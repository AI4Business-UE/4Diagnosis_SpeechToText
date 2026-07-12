# Ewaluacja STT

Ten plik opisuje lokalny eval STT dla projektu 4Diagnosis SpeechToText: skąd bierzemy dane, jak odpalić ewaluację i jak czytać metryki.

## Dane

Dane źródłowe są trzymane poza repozytorium: [folder Google Drive](https://drive.google.com/drive/folders/1J5VXlJVQQC9Qi66E2UWqxaaoEeCy17uU).

Audio kopiujemy lokalnie do:

```text
backend/eval/data/stt/audio_samples
```

Pliki audio są ignorowane przez Git i nie powinny trafiać na GitHuba.

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

Ten plik jest ignorowany przez Git, bo może zawierać lokalne ścieżki i referencyjne transkrypcje.

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

## Definicje metryk

- `WER` (`Word Error Rate`) - błąd na poziomie słów, liczony **z ujednoliceniem zapisu liczb** (`5,5` = `5.5`, a `3,5 x 3,0 x 3,5` to jeden token). Im niżej, tym lepiej. `0.0` oznacza brak błędów.
- `CER` (`Character Error Rate`) - błąd na poziomie znaków, również z ujednoliceniem liczb. Im niżej, tym lepiej.
- `wer_strict` / `cer_strict` - te same metryki, ale **bez ujednolicenia zapisu liczb** — karzą różnicę formatu (`5,5` vs `5.5`). Porównanie z `WER`/`CER` pokazuje, ile błędu bierze się z samego zapisu, a ile z realnego przekręcenia słów.
- `number_recall` - ile liczb z referencji model przepisał poprawnie. Im bliżej `1.0`, tym lepiej.
- `dimension_recall` - ile wymiarów z referencji model przepisał poprawnie, np. `1,5 cm` albo `3 x 2 cm`. Im bliżej `1.0`, tym lepiej.
- `medical_term_recall` - ile terminów medycznych ze słownika projektu, obecnych w referencji, pojawiło się też w transkrypcji. Im bliżej `1.0`, tym lepiej.
- `pesel_accuracy` - dokładność PESEL-u, jeśli PESEL występuje w referencji. `1.0` oznacza idealne dopasowanie, `0.0` błąd, a pusta wartość oznacza brak PESEL-u w referencji.
- `has_critical_error` - czy próbka ma **twardy** błąd krytyczny: w liczbach, wymiarach albo PESEL-u (kategorie exact-match, wysokiej stawki). Terminologia medyczna jest liczona osobno (patrz `has_term_error`).
- `critical_error_count` - liczba twardych kategorii krytycznych (liczby / wymiary / PESEL) z błędem dla jednej próbki.
- `has_term_error` - czy próbka zgubiła jakiś termin medyczny obecny w referencji (kategoria miękka, śledzona osobno od błędów twardych).
- `duration_seconds` - całkowity czas przetwarzania jednej próbki.
- `audio_duration_seconds` - długość pliku audio.
- `real_time_factor` - stosunek czasu przetwarzania do długości audio. `3.0` oznacza, że przetwarzanie trwało 3 razy dłużej niż samo audio.
- `errors_count` - liczba próbek, które zakończyły się błędem technicznym dla danej konfiguracji.

## Komendy

Eval najlepiej odpalać przez backendowy venv:

```bash
backend/venv/bin/python backend/eval/build_stt_manifest.py
```

Mały smoke eval:

```bash
backend/venv/bin/python backend/eval/run_stt_eval.py \
  --limit 1 \
  --models whisper-small \
  --preprocessing baseline
```

Większy run na wybranych modelach i konfiguracjach:

```bash
backend/venv/bin/python backend/eval/run_stt_eval.py \
  --models whisper-small whisper-medical-pl \
  --preprocessing baseline vad noise_reduction
```

Podsumowanie wyników:

```bash
backend/venv/bin/python backend/eval/summarize_stt_results.py \
  --input backend/eval/results/stt_eval_results.csv \
  --output backend/eval/results/stt_eval_summary.csv
```

Porównanie aktualnego runu z baseline:

```bash
backend/venv/bin/python backend/eval/compare_stt_baseline.py \
  --current backend/eval/results/stt_eval_results.csv \
  --baseline backend/eval/baselines/stt/whisper_comparison_results.csv \
  --output backend/eval/results/stt_baseline_comparison.csv
```

NER eval na referencyjnych transkryptach:

```bash
backend/venv/bin/python backend/eval/run_ner_eval.py \
  --input backend/eval/data/ner/ner_eval_samples.jsonl \
  --strategies chained split \
  --output backend/eval/results/ner_eval_results.csv
```

Podsumowanie NER:

```bash
backend/venv/bin/python backend/eval/summarize_ner_results.py \
  --input backend/eval/results/ner_eval_results.csv \
  --output backend/eval/results/ner_eval_summary.csv
```

End-to-end eval, czyli audio -> STT -> NER, odpalać tylko na małym limicie:

```bash
backend/venv/bin/python backend/eval/run_end_to_end_eval.py \
  --limit 1 \
  --models whisper-small \
  --preprocessing baseline \
  --ner-strategies chained \
  --output backend/eval/results/end_to_end_eval_results.csv
```

Prosty raport markdown z dostępnych wyników:

```bash
backend/venv/bin/python backend/eval/generate_eval_report.py \
  --output backend/eval/results/eval_report.md
```

## Co commitować

Można commitować:

- kod evala,
- dokumentację,
- baseline CSV,
- świadomie wybrane wyniki CSV, jeśli nie zawierają danych wrażliwych.

Nie commitować:

- audio,
- metadanych lokalnych,
- `stt_manifest.csv`,
- `preprocessed_audio`
