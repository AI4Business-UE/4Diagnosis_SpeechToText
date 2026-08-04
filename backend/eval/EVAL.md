# Ewaluacja pipeline'u

Ten eval jest po to, żeby szybko sprawdzić, czy pipeline 4Diagnosis działa sensownie:

```text
audio -> STT -> NER -> formularz -> sanity check
```

## Jak odpalić

Najpierw ustawiasz `backend/eval/config.yaml`, potem odpalasz:

```bash
backend/venv/bin/python backend/eval/run_eval.py
```

Możesz też jednorazowo nadpisać stage z terminala:

```bash
backend/venv/bin/python backend/eval/run_eval.py --stages end_to_end
```

Jeśli run używa NER albo `sanity_modes: [rules_and_llm]`, wczytaj wcześniej klucze:

```bash
set -a; source backend/env; set +a
```

## Który stage wybrać

Na co dzień najczęściej wystarczy:

```yaml
stages: [end_to_end]
```

To jest normalny eval end-to-end: bierze audio, robi STT, potem NER, buduje formularz i puszcza
sanity check. Jeśli wejście ma referencje (`ref_transcript`, `expected_entities`), w tym samym
wyniku pojawią się też metryki STT i NER z prefiksami `stt_` oraz `ner_`.

Sanity check ma tryby wybierane w `config.yaml`:

```yaml
sanity_modes: [rules]
```

`rules` to deterministyczny baseline bez sieci. Do eksperymentu porównawczego możesz ustawić:

```yaml
sanity_modes: [rules, rules_and_llm]
```

Wtedy eval zapisze osobny wiersz dla każdego trybu. `rules_and_llm` odpala reguły, a potem opcjonalny
LLM review; wymaga klucza API i może generować koszt.

Pozostałe stage'e są głównie do debugowania:

- `stt` - gdy chcesz sprawdzić samą transkrypcję, bez NER.
- `ner` - gdy chcesz sprawdzić sam NER na gotowych, poprawnych transkryptach.
- `[stt, ner, end_to_end]` - gdy robisz pełną diagnostykę. To działa, ale częściowo się dubluje,
  bo `end_to_end` i tak przechodzi przez STT oraz NER.

Jeśli chcesz wiedzieć, czy cały system działa, odpal `end_to_end`. Jeśli coś jest
źle, dopiero wtedy odpal osobno `stt` albo `ner`, żeby znaleźć winnego.

## Dane i wyniki

Dane wejściowe są lokalne i nie idą do repo:

```text
backend/eval/data/
├── audio_samples/                 # nagrania
├── metadata/samples_metadata.xlsx # metadane do audio
├── gold_audio.csv                 # audio + referencje STT/NER
├── gold_ner.jsonl                 # transkrypty + oczekiwane encje
└── plausibility_fixture.jsonl     # gotowe formularze do sanity check
```

Nagrania i metadane są trzymane poza repo: [folder Google Drive](https://drive.google.com/drive/folders/1J5VXlJVQQC9Qi66E2UWqxaaoEeCy17uU).

Całe `backend/eval/data/` jest ignorowane przez Git. Wyniki też są lokalne:

```text
backend/eval/results/
├── stt_results.csv
├── ner_results.csv
└── end_to_end_results.csv
```

`end_to_end_input` w `config.yaml` decyduje, co dokładnie testuje end-to-end:

- CSV z `audio_path` - pełny pipeline od audio.
- JSONL z `form_data` - sam sanity check na gotowym formularzu, bez STT/NER.
- plik z `expected_entities` - formularz składany z gold encji, czyli wariant offline.

## Jak czytać wyniki

W STT najważniejsze są:

- `wer` / `cer` - ogólny błąd transkrypcji; im niżej, tym lepiej.
- metryki liczb, wymiarów i PESEL-u - tu błędy są ważniejsze niż literówki.
- `has_critical_error` - szybka flaga, że próbka ma twardy błąd w czymś istotnym.

W NER patrz głównie na:

- `precision` - czy model nie dopisuje rzeczy, których nie było.
- `recall` - czy model nie pomija rzeczy, które powinien znaleźć.
- `f1` - jedna liczba do porównywania wariantów.
- metryki per encja, np. osobno dla pacjenta, komponentów, zmian i płynów.

W sanity check najważniejsze są:

- `sanity_mode` - `rules` albo `rules_and_llm`.
- `status` - `ok`, `warning` albo `critical`.
- `score` - szybka liczba jakości; im bliżej `1`, tym lepiej.
- `issue_count` / `issue_codes` - co konkretnie zostało wykryte.
- `llm_ran`, `llm_reason`, `llm_issue_count` - czy LLM review realnie się wykonał i co zwrócił.

Domyślny runtime hidden logging w backendzie dalej używa `rules`, więc nie robi ukrytej sieci.

Jeśli `end_to_end_results.csv` ma kolumny z prefiksem `stt_` albo `ner_`, to znaczy, że eval liczył
te metryki przy okazji pełnego runu.

## Czego nie commitować

Commitujemy kod i dokumentację evala.

Nie commitujemy:

- `backend/eval/data/` - audio, metadanych ani gold setów,
- `backend/eval/results/` - lokalnych wyników,
- `backend/env` - kluczy i sekretów.
