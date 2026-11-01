# Ewaluacja pipeline'u transkrypcji

To jest lokalny runner end-to-end dla `Pipeline.run()`. Nie uruchamia Django test runnera ani pytest; Django inicjalizuje wyłącznie po to, by etap STT mógł odczytać lokalny katalog `Keyword`.

## Instalacja i przygotowanie referencji NER

Uruchom z katalogu `backend`. Wymagane są również zależności projektu z `requirements.txt`:

```bash
python -m pip install -r requirements.txt
python -m pip install -r eval/requirements.txt
python eval/run.py --init-ner-references
```

Polecenie tworzy ignorowany przez Git plik `eval/data/golden_dataset/ner_references.json`, bez kopiowania tekstu klinicznego z arkusza. Uzupełnij go ręcznie, sprawdzając kolumnę `oczekiwany output` w `samples_metadata.xlsx`. Zapis powinien mieć postać:

```json
{
  "version": 1,
  "samples": {
    "001": {
      "reviewed": true,
      "entities": {
        "patient": {
          "first_name": null,
          "last_name": null,
          "pesel": null,
          "age": null
        },
        "components": [],
        "lesions": [],
        "fluid_samples": []
      }
    }
  }
}
```

Uzupełnij wszystkie identyfikatory wybrane do danego uruchomienia i ustaw `reviewed` na `true` dopiero po sprawdzeniu adnotacji. Klucze encji odpowiadają schematowi pipeline'u. Pole pominięte w obiekcie encji oznacza **nieznane/nieoceniane**; jawne `null` oznacza znany brak wartości; pusta lista oznacza brak encji w danej kategorii. Nie wyciągaj informacji, których nie ma w oczekiwanym output. Każda próbka musi zawierać kategorie `patient`, `components`, `lesions` i `fluid_samples`.

Numerowane sekcje komponentów i zmian zapisuj jako osobne obiekty na listach; numer sekcji nie jest `count` ani `component_index`. Gdy wymiar jest uzupełniony, podaj również jednostkę `cm` lub `mm`.

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

WER i CER porównują surowy transkrypt z `tekst referencyjny`; raportowany jest wynik pooled dla całego wybranego zbioru. NER porównuje wynik pipeline'u z lokalnymi adnotacjami JSON. Sędzia ocenia wierność `corrected_transcript` wobec tekstu referencyjnego w skali 0–4, bez niezależnej oceny poprawności medycznej.

Raport zbiorczy trafia domyślnie do `eval/results/` (ignorowanego przez Git). Teksty próbek, dane encji i uzasadnienia sędziego są zapisywane tylko z `--include-details`; taki raport zawiera dane kliniczne i powinien pozostać lokalny. Błędy pojedynczych próbek nie zatrzymują zbioru, ale niekompletna ewaluacja kończy się kodem 1. Wyniki nie mają obecnie progów zaliczenia.
