# Ewaluacja pipeline'u transkrypcji

To jest lokalny runner end-to-end dla `Pipeline.run()`. Nie uruchamia Django test runnera ani pytest; Django inicjalizuje wyłącznie po to, by etap STT mógł odczytać lokalny katalog `Keyword`.

## Instalacja

Uruchom z katalogu `backend`. Wymagane są również zależności projektu z `requirements.txt`:

```bash
python -m pip install -r requirements.txt
python -m pip install -r eval/requirements.txt
```

## Uruchomienie

Pełna ścieżka używa STT, NER, answerera oraz sędziego LLM. Zatwierdź użycie skonfigurowanych usług przed wysłaniem do nich nagrań i tekstów klinicznych:

```bash
EVAL_JUDGE_MODEL=openai/gpt-4o python eval/run.py --allow-external-data
```

Wymagane są również istniejąca lokalna baza Django z tabelą `Keyword` oraz `OPENROUTER_API_KEY` lub `OPENAI_API_KEY`. Sędzia jest domyślnie włączony; jego model można wskazać przez `EVAL_JUDGE_MODEL` albo `--judge-model`. Aby pominąć wyłącznie ocenę sędziego, użyj `--no-judge` — pozostałe etapy nadal mogą wysyłać dane do usług zewnętrznych.

Domyślnie runner przetwarza wszystkie 80 rekordów, używa konfiguracji `PipelineConfig` i izolowanego Qdrant in-memory z lokalnymi makro-szablonami. Przykładowe opcje:

```bash
python eval/run.py --allow-external-data --samples 001,002 --stt-model whisper_local --no-judge
python eval/run.py --allow-external-data --include-details --output eval/results/sample-review.json
```

## Ocena metadanych pacjenta

Arkusz `data/golden_dataset/samples_metadata.xlsx` zawiera opcjonalne kolumny referencyjne metadanych pacjenta: `imię pacjenta`, `nazwisko pacjenta`, `wiek` i `PESEL`. Pusta komórka (także pusty tekst) oznacza brak referencji dla tego pola — pole nie jest wtedy oceniane. Runner przy każdym uruchomieniu deterministycznie porównuje surowy wynik NER (`entities.patient`) z tymi referencjami:

- imię i nazwisko: dopasowanie bez rozróżnienia wielkości liter i z zawężeniem odstępów;
- wiek: równość liczb całkowitych;
- PESEL: równość 11-cyfrowych ciągłów (komórki liczbowe są dopełniane zerami wiodącymi, bo Excel gubi zera).

Wartości sprzeczne z tymi regułami (wiek nie-całkowity, PESEL inny niż 11 cyfr) przerywają uruchomienie błędem walidacji arkusza. Każde oceniane pole próbki otrzymuje 1 (poprawnie) lub 0 (błąd lub brak ekstrakcji); wynik próbki to suma poprawnych pól podzielona przez liczbę pól ustawionych w referencji. Próbka z błędem pipeline'u otrzymuje zera za wszystkie ustawione pola i pozostaje w średniej. Próbki bez żadnych metadanych nie wpływają na średnią.

WER i CER porównują surowy transkrypt z `tekst referencyjny`; raportowany jest wynik pooled dla całego wybranego zbioru. Sędzia ocenia wierność `corrected_transcript` wobec tekstu referencyjnego w skali 0–4, bez niezależnej oceny poprawności medycznej.

## Raporty

Każde uruchomienie zapisuje raport zbiorczy JSON oraz arkusz przeglądu `.xlsx` z datą i godziną w ignorowanym przez Git katalogu `eval/results/`. Arkusz zawiera po jednym wierszu na próbkę (także nieudaną), status, surowy transkrypt, końcowy obiekt encji NER i skorygowany transkrypt. Podsumowanie `patient_metadata` w raporcie JSON zawiera `samples`, `mean_score` oraz rozbicie `fields` (`correct`/`graded` per pole); wiersz podsumowania CLI pokazuje `metadane pacjenta: <średnia> (<n> próbek)`, gdy choć jedna próbka ma metadane. Arkusz jest lokalnym, wrażliwym wynikiem ewaluacji — nie przenoś go poza zaufane środowisko. Błąd zapisu arkusza oznacza nieudaną ewaluację (kod 1).

Podsumowanie metadanych pacjenta jest raportowane jako kolumny `Imię pacjenta zgodne`, `Nazwisko pacjenta zgodne`, `Wiek zgodny`, `PESEL zgodny` (1/0, puste gdy pole nieoceniane) oraz `Wynik metadanych pacjenta (0–1)` w arkuszu przeglądu.

Arkusz przeglądu zawiera również osobny status sędziego LLM, wynik 0–4, uzasadnienie, pominięcia, dodatki, sprzeczności oraz powód pominięcia — bez nadpisywania statusu próbki. Tablice problemów sędziego są wyświetlane jako tekst rozdzielony nowymi wierszami. Opcjonalna kolumna metadanych `oceniaj sędzią LLM` przyjmuje wyłącznie wartości logiczne: `FALSE` pomija sędziego dla próbki, a `TRUE`, pusta komórka lub brak kolumny pozostawia ocenę włączoną. Opcjonalny tekst w `powód pominięcia sędziego` jest dozwolony wyłącznie dla próbki z `FALSE`. Próbki pominięte na tym poziomie nadal przechodzą przez pipeline i pozostają w arkuszu, ale nie wpływają na statystyki sędziego. Globalne `--no-judge` jest raportowane odrębnie; brak ocen nie powoduje sam w sobie niekompletności ewaluacji.

Teksty próbek, dane encji i uzasadnienia sędziego trafiają do raportu JSON tylko z `--include-details`; taki raport zawiera dane kliniczne i powinien pozostać lokalny. Błędy pojedynczych próbek nie zatrzymują zbioru, ale niekompletna ewaluacja kończy się kodem 1. Wyniki nie mają obecnie progów zaliczenia.

Raport szczegółowy można zapisać wyłącznie pod `eval/results/`, aby nie trafił przypadkowo do śledzonych plików.
