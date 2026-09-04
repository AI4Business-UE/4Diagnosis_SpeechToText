# Ewaluacja pipeline'u

Ten eval jest po to, żeby szybko sprawdzić, czy pipeline 4Diagnosis działa sensownie:

```text
audio -> STT -> NER -> RAG/answerer -> formularz -> sanity check
```

Szczegóły działania guardraila są opisane w
`backend/src/app_stt/services/DATA_SANITY_CHECK.md`.

## Jak odpalić

Wszystkie komendy odpalaj z katalogu głównego repo (`4Diagnosis_SpeechToText`) — ścieżki są
względne do niego. Wykonaj kroki po kolei.

### 0. Instalacja zależności

Eval uruchamia prawdziwy pipeline (Whisper, NER, RAG), więc potrzebuje pakietów z obu plików
wymagań — bazowego i eval:

```bash
python3 -m pip install -r backend/requirements.txt -r backend/eval/requirements-eval.txt
```

To duże pobieranie (torch, transformers, qdrant-client, sentence-transformers — kilka GB).
Najlepiej w wirtualnym środowisku (venv).

### 1. Klucze API

Potrzebne do NER (etapy `ner` i `end_to_end`) oraz do trybów LLM sanity (`rules_and_llm`,
`review_and_repair`). Wczytaj raz na sesję terminala:

```bash
set -a; source backend/env; set +a
```

Sam sanity `rules` i wariant offline (krok 5) klucza nie wymagają.

### 2. Qdrant (dla `end_to_end` z audio)

Pełny `end_to_end` przechodzi przez RAG, więc potrzebuje Qdranta z zaindeksowaną kolekcją:

```bash
colima start
docker-compose up -d qdrant
cd backend/src
PYTHONPATH=. python3 manage.py index_qdrant
cd ../..
```

### 3. Konfiguracja

Ustaw etapy i parametry w `backend/eval/config.yaml` (co wybrać — patrz „Który stage wybrać").

### 4. Uruchomienie

Bierze `stages` z `config.yaml` (to, co zostało ustawione w kroku 3):

```bash
PYTHONPATH=backend/src:backend/eval python3 backend/eval/run_eval.py
```

Wyniki lądują w `backend/eval/results/` (osobny CSV per etap).

### 5. Wariant offline — sam sanity guardrail

Jeśli chcesz tylko sanity, bez audio / Whispera / NER / RAG (a więc bez kroków 1–2), ustaw w
`config.yaml` w sekcji `paths`:

```yaml
paths:
  end_to_end_input: data/sanity_guardrail_eval_gold.jsonl
```

i odpal tę samą komendę co w kroku 4.

## Odpalanie „po trochu" (checkpoint + wznawianie)

Pełny eval każdej kombinacji (modele × preprocessing × strategie NER × tryby sanity × próbki)
bywa długi i potrafi się zablokować (pobranie modelu, sieć, wywołanie LLM). Dwa mechanizmy
pozwalają liczyć etapami i nie tracić postępu:

- **checkpoint** (`checkpoint_every: 1` w configu) — po każdym gotowym wierszu dopisuje częściowy
  `results/*.csv`, więc po `Ctrl+C` albo blokadzie masz już policzone wyniki na dysku.
- **wznawianie** (`resume: true`, domyślnie włączone) — przy starcie czyta istniejący
  `results/*.csv`, pomija kombinacje już policzone i dokłada tylko brakujące. Klucz jednostki:
  `próbka + model + preprocessing + strategia NER + tryb sanity`.

Dzięki temu typowy przepływ to po prostu **odpalaj tę samą komendę, aż policzy wszystko**:

```bash
# ustaw pełną macierz w config.yaml (np. models: [...], preprocessing: [...], limit: null),
# a potem odpalaj ile razy trzeba — każde uruchomienie dokłada brakujące:
PYTHONPATH=backend/src:backend/eval python3 backend/eval/run_eval.py
```

Jeśli coś się zablokuje (mi się zawieszało pomiędzy modelami): przerwij (`Ctrl+C`) i odpal ponownie tę samą komendę — pominie zrobione,
policzy resztę. Chcesz liczyć od zera i nadpisać wyniki: `--no-resume` (albo `resume: false`).

### Przerywanie i wznawianie ręczne

Możesz spokojnie kończyć działanie kodu w trakcie i dopalać partiami:

- **`Ctrl+C` jest bezpieczne.** `checkpoint_every: 1` zapisuje CSV po każdym gotowym wierszu, a zapis
  jest atomowy (plik `.tmp` + podmiana), więc `results/*.csv` nigdy nie jest w połowie zapisany —
  masz albo starą, albo nową kompletną wersję.
- **Tracisz maksymalnie jeden wiersz** — ten liczony w momencie przerwania (i tak nie był zapisany).
  Przy wznowieniu policzy się od nowa.
- **Możesz wznawiać ten sam config.** Przy `resume: true` eval czyta istniejący CSV,
  pomija kombinacje, które już są zapisane, i liczy tylko brakujące wiersze.
- **Możesz też rozszerzać config między przebiegami**, np. dodać nowy `model`,
  `preprocessing` albo zwiększyć `limit`. Wtedy stare kombinacje zostaną pominięte,
  a eval doliczy tylko nowe.
- **Jeśli zawężasz config**, np. usuwasz `model`, `preprocessing` albo tryb sanity,
  stare wiersze zostaną w CSV. To nie psuje pliku, ale przy analizie trzeba filtrować
  wyniki po aktualnym configu. Jeśli chcesz czysty wynik od zera, uruchom z `--no-resume`
  albo usuń odpowiedni plik z `results/`.

- **Przerwanie podczas pobierania Whispera albo ładowania modelu jest OK.**
  Jeśli żaden wiersz nie został jeszcze zapisany, po prostu odpal eval ponownie.
- **Używaj `Ctrl+C` (SIGINT), nie `kill -9`** w trakcie zapisu — SIGINT zawsze zostawia spójny plik.

Tryb pracy: ustaw macierz → odpalaj, przerywaj, odpalaj ponownie, aż `results/*.csv` się zapełni.

### Kiedy przerwać (a kiedy nie)

**Nie zatrzymuj evala „na timer".** Restart nic nie przyspiesza, a od nowa ładuje model Whisper
(strata czasu). Puść go i zostaw — checkpoint i tak zapisuje każdy wiersz na bieżąco.
Przerywaj `Ctrl+C` **tylko** gdy realnie się zablokuje.

Jak poznać zwis: patrz, czy przybywa wierszy w wynikowym CSV. Jedna próbka `end_to_end` to
orientacyjnie ~30 s–2 min (STT + kilka wywołań LLM). Zasada kciuka:

> jeśli liczba wierszy **nie rośnie przez ~3–5 min** → coś stoi (sieć / LLM / Qdrant /
> pobieranie modelu). Wtedy `Ctrl+C` i odpal tę samą komendę — resume dokończy resztę.

Wyjątek: **pierwsze** uruchomienie pobiera model Whisper (kilka minut, wygląda jak zwis, bez
nowych wierszy) — to normalne, nie przerywaj.

### Podgląd postępu

Na żywo, co 5 s (`Ctrl+C` wychodzi z podglądu, nie rusza evala). Każdy etap ma **swój plik i swój
licznik** — `end_to_end` idzie do `end_to_end_results.csv`, `ner` do `ner_results.csv`.

**end_to_end** (`N / models×preprocessing×ner×sanity×limit`):

```bash
TOTAL=$(python3 -c "import yaml;c=yaml.safe_load(open('backend/eval/config.yaml'));s=c.get('sanity_repair_scopes') or ['all'];runs=sum(len(s) if m=='review_and_repair' else 1 for m in (c.get('sanity_modes') or ['rules']));lim=c['limit'] if c['limit'] is not None else 80;print(len(c['models'])*len(c['preprocessing'])*len(c['ner_strategies'])*runs*lim)")
watch -n 5 "echo \"end_to_end: \$(( \$(wc -l < backend/eval/results/end_to_end_results.csv 2>/dev/null || echo 1) - 1 )) / $TOTAL\"; tail -1 backend/eval/results/end_to_end_results.csv 2>/dev/null | cut -d, -f1-5"
```

**ner** (`N / ner_strategies×limit`):

```bash
NER_TOTAL=$(python3 -c "import yaml;c=yaml.safe_load(open('backend/eval/config.yaml'));lim=c['limit'] if c['limit'] is not None else 80;print(len(c['ner_strategies'])*lim)")
watch -n 5 "echo \"ner: \$(( \$(wc -l < backend/eval/results/ner_results.csv 2>/dev/null || echo 1) - 1 )) / $NER_TOTAL\"; tail -1 backend/eval/results/ner_results.csv 2>/dev/null | cut -d, -f1-4"
```

## Który stage wybrać

Na co dzień najczęściej wystarczy:

```yaml
stages: [end_to_end]
limit: 1
sanity_modes: [rules]
```

To jest normalny eval end-to-end: bierze audio i idzie tą samą ścieżką co aplikacja do momentu
formularza, czyli `Pipeline.run()` robi STT, NER, RAG/answerer i buduje `form_data`. W evalu
pipeline'owe sanity jest wyłączone, a wybrane `sanity_modes` są liczone później na tym samym
`corrected_transcript` i `form_data`. Dzięki temu porównanie `rules`, `rules_and_llm` i
`review_and_repair` jest robione na identycznym wyniku pipeline'u. Domyślne wejście
(`samples_metadata.xlsx`) ma `tekst referencyjny`, więc dochodzą metryki STT z prefiksem `stt_`.
Metryk `ner_` tam nie ma — xlsx nie niesie gold-encji; jakość NER mierzysz osobno w etapie `ner`
(precision/recall/f1 per encja, na `gold_ner.jsonl`; bez audio i Qdranta). Wystarczy mieć `ner`
w `stages` (krok 3) — wtedy zwykłe `run_eval.py` z kroku 4 policzy go do `ner_results.csv`.

Sanity check ma tryby wybierane w `config.yaml`:

```yaml
sanity_modes: [rules]
sanity_repair_scopes: [all]
```

`rules` to deterministyczny baseline bez sieci. Do eksperymentu porównawczego możesz ustawić:

```yaml
sanity_modes: [rules, rules_and_llm, review_and_repair]
sanity_repair_scopes: [patient_data, description, all]
```

Wtedy eval zapisze osobny wiersz dla każdego trybu. `rules_and_llm` odpala reguły, a potem opcjonalny
LLM review. `review_and_repair` odpala LLM repair i pokazuje, czy poprawki zmniejszają liczbę
warningów. Oba tryby LLM wymagają klucza API i mogą generować koszt.

Zakresy repair:

- `patient_data` - LLM może poprawić `name`, `age`, `pesel`,
- `description` - LLM może poprawić `organ`, `description`,
- `all` - LLM może poprawić wszystkie pola formularza.

Pozostałe stage'e są głównie do debugowania:

- `stt` - gdy chcesz sprawdzić samą transkrypcję, bez NER.
- `ner` - gdy chcesz sprawdzić sam NER na gotowych, poprawnych transkryptach.
- `[stt, ner, end_to_end]` - gdy robisz pełną diagnostykę. To działa, ale częściowo się dubluje,
  bo `end_to_end` i tak przechodzi przez STT oraz NER.

Jeśli chcesz wiedzieć, czy cały system działa, odpal `end_to_end`. Jeśli coś jest
źle, dopiero wtedy odpal osobno `stt` albo `ner`, żeby znaleźć winnego.

Uwaga: `limit` to liczba próbek **na każdą kombinację** (model × preprocessing × strategia NER ×
tryb sanity), **nie łącznie**. Liczba wierszy w wyniku = iloczyn wszystkich list × `limit`
(np. `models:5 × preprocessing:5 × ner:2 × sanity:3 × limit:10 = 1500`; `limit: null` = wszystkie 80).

Najbezpieczniejsza kolejność testowania:

- najpierw `limit: 1`, `sanity_modes: [rules]`,
- potem `limit: 3`,
- potem `limit: 10`,
- dopiero na końcu tryby z LLM: `rules_and_llm` albo `review_and_repair`.

## Dane i wyniki

Dane audio, metadane i wyniki są lokalne.

```text
backend/eval/data/
├── audio_samples/                 # nagrania
├── metadata/samples_metadata.xlsx # end_to_end: audio + tekst referencyjny (bez gold NER)
├── gold_ner.jsonl                 # ner (teksty BEZ audio): transcript + expected_entities
└── sanity_guardrail_eval_gold.jsonl # sanity guardrail: gotowe formularze + oczekiwane flagi
```

Dwa niezależne zestawy gold:

- **`metadata/samples_metadata.xlsx`** - wejście `end_to_end`. Kolumny `nazwa pliku` + `tekst referencyjny`
  (audio + referencja STT). Do tych próbek mamy audio, więc idzie tu pełny pipeline i metryki STT.
  Kolumna `synthetic` (TRUE/puste) oznacza audio TTS z fikcyjnym PESEL-em — dla takich próbek eval
  automatycznie wycisza w raporcie issue PESEL/wieku (patrz `synthetic_ignored_issues` w configu),
  bo to szum, nie błąd pipeline'u. Cały ten zbiór jest testowy, więc wszystkie próbki są `synthetic`.
  Można też dodać kolumnę `ignored_sanity_issues` (format `code:field|...`), która ma pierwszeństwo.
- **`gold_ner.jsonl`** - wejście `ner`. Linie `{sample_id, transcript, expected_entities}`; testuje sam
  NER na czystym tekście (bez audio i błędów STT), liczy precision/recall/f1 per encja. Rozwijaj go
  niezależnie - możesz dodawać przypadki tekstowe, do których nie ma nagrań.

Nagrania i metadane są trzymane poza repo: [folder Google Drive](https://drive.google.com/drive/folders/1Tk1E5TOWss6PAEgUyWfCR9oPPLAYIyRQ).

Wyniki też są lokalne:

```text
backend/eval/results/
├── stt_results.csv
├── ner_results.csv
└── end_to_end_results.csv
```

`end_to_end_input` w `config.yaml` decyduje, co dokładnie testuje end-to-end:

- XLSX (`samples_metadata.xlsx`) - domyślnie: pełny pipeline od audio do `form_data` na wszystkich
  próbkach, z metrykami STT (vs `tekst referencyjny`) i wybranymi sanity modes.
- CSV z `audio_path` - pełny pipeline od audio do `form_data`, potem eval liczy wybrane sanity modes.
- JSONL z `form_data` - sam sanity check na gotowym formularzu, bez STT/NER.
- plik z `expected_entities` - formularz składany z gold encji, czyli wariant offline.

Etap `ner` jest osobny: `ner_gold` wskazuje na `data/gold_ner.jsonl` (transcript + expected_entities)
i testuje sam NER na czystym tekście, bez audio i błędów STT.

Do samego sanity guardraila używaj `data/sanity_guardrail_eval_gold.jsonl`. Tam PESEL i wiek są
normalnie oceniane, bo formularz jest kontrolowany ręcznie.

## Jak czytać wyniki

`end_to_end_results.csv` jest głównym wynikiem: tu patrzysz na metryki STT/NER, status pipeline'u
i wynik sanity.

Gotowy raport (STT per model/preprocessing, macierz WER, latencja, zachowanie sanity) — działa też
na częściowym CSV, więc możesz go odpalać w trakcie runu:

```bash
python3 backend/eval/analyze_results.py
```

W lokalnym raporcie eval drukuje też rozkład `suspected_stage` i `stage_warning_reason`.
To odpowiada na pytanie, gdzie najczęściej zaczynają się problemy:

- `pipeline` - pełny pipeline rzucił wyjątek,
- `stt` - brak transkryptu,
- `ner` - brak encji,
- `rag` - brak template'ów,
- `answerer` - brak corrected text,
- `form_data` - brakuje `organ` albo `description`,
- `sanity` - formularz przeszedł pipeline, ale guardrail zgłosił warning/critical,
- `ok` - brak podejrzanego sygnału v1.

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

- `sanity_mode` - `rules`, `rules_and_llm` albo `review_and_repair`.
- `suspected_stage` / `stage_warning_reason` - gdzie eval v1 podejrzewa źródło problemu.
- `status` - `ok`, `warning` albo `critical`.
- `score` - szybka liczba jakości; im bliżej `1`, tym lepiej.
- `issue_count` / `issue_codes` - co konkretnie zostało wykryte.
- `expected_flag` - czy guardrail miał w ogóle coś zgłosić.
- `expected_issue_codes_covered` - czy guardrail wykrył wszystkie oczekiwane typy problemów.
- `expected_severity` / `severity_match` - pomocnicza kalibracja score i wag.
- `raw_issue_codes` - co guardrail zgłosił *przed* wyciszeniem (np. issue PESEL na próbce `synthetic`).
- `ignored_sanity_issues` / `ignored_sanity_issue_count` - co i ile wyciszono w raporcie
  (dla próbek `synthetic` domyślnie kody PESEL/wieku).
- `llm_ran`, `llm_reason`, `llm_issue_count` - czy LLM review realnie się wykonał i co zwrócił.
- `repair_scope`, `repair_ran`, `repair_applied`, `repair_changed_fields` - czy LLM repair
  realnie coś poprawił i w jakim zakresie.

Główne kryteria poprawności guardraila w v1 to `expected_flag` i
`expected_issue_codes_covered`. `expected_severity` traktuj jako sygnał do kalibracji scoringu,
nie jako twarde przejście/nieprzejście całego sanity checka.

Domyślny runtime hidden logging w backendzie dalej używa `rules`, więc nie robi ukrytej sieci.
Repair w aplikacji też jest opt-in: formularz jest zmieniany tylko, gdy pipeline ma jawnie ustawione
`sanity_mode="review_and_repair"` i `apply_sanity_repair=True`.

`review_and_repair` jest trybem eksperymentalnym. Wysyła transkrypt i tylko pola formularza
dozwolone przez `repair_scope` do zewnętrznego LLM, więc przy `patient_data` albo `all` może
obejmować dane pacjenta. Do normalnego lokalnego smoke testu i do domyślnego runtime’u używaj
`rules`; repair włączaj tylko świadomie, gdy testujesz poprawianie danych.

Jeśli `end_to_end_results.csv` ma kolumny z prefiksem `stt_` albo `ner_`, to znaczy, że eval liczył
te metryki przy okazji pełnego runu.

## Czego nie commitować

Commitujemy kod, dokumentację evala i, jeśli ma być wspólnym punktem odniesienia dla zespołu,
`backend/eval/data/sanity_guardrail_eval_gold.jsonl`.

Nie commitujemy:

- `backend/eval/data/audio_samples/` - nagrań,
- `backend/eval/data/metadata/` - lokalnych metadanych (w tym `samples_metadata.xlsx` z goldem),
- `backend/eval/results/` - lokalnych wyników,
- `backend/env` - kluczy i sekretów.
