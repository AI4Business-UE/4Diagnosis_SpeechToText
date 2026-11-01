import logging

from .base import Answerer
from app_stt.pipeline.utils.llm.client import get_llm_client


logger = logging.getLogger(__name__)

PROMPT = """
    ## Rola i Cel
    Jesteś profesjonalnym systemem korekty transkrypcji badań patomorfologicznych. Otrzymujesz na wejściu 
    zaszumioną transkrypcję (błędy fonetyczne, homophony i literówki) i pozbywasz się szumu by na wyjściu 
    otrzymać czysty i semantycznie poprawny raport lekarski. 

    ## Główne zasady
    1. ZERO HALUCYNACJI: Nie dodawaj absolutnie żadnych informacji, wymiarów ani diagnoz, których nie ma w oryginalnej transkrypcji.
    2. BŁĘDY FONETYCZNE ASR: Koryguj ewidentne błędy fonetyczne transkrypcji, przy czym kieruj się logiką kliniczną oraz kontekstem anatomicznym, na poprawne terminy medyczne i anatomiczne (np. "szon macicy" -> "trzon macicy", "lito o wymiarach" -> "jelito o wymiarach", "narko" -> "nerka").
    3. POSTĘPOWANIE Z BRAKAMI: Jeśli jakikolwiek fragment dyktanda jest całkowicie niezrozumiały lub brakuje w nim sensu w kontekście logiki klinicznej lub anatomii, **nie zgaduj jego treści**. Wstaw w tym miejscu znacznik [NIEZROZUMIAŁE].
    4. AUTOKOREKTA LEKARZA: Lekarz może poprawiać się w trakcie dyktowania (np, "dwa, nie, przepraszam osiem centrymetrów"). Śledź ten tok myślenia i zapisz tylko ostateczną wartość.
    5. BŁĘDY ORTOGRAFICZNE ASR: Koryguj błędy ortograficzne 
    6. USUWANIE SZUMU: Pomiń wszelkie wypowiedzi niebędące częścią badania (np. "dobra, zaczynamy", "halo", chrząknięcia, jąkanie). Wszystkio co bezpośrednio opisuje komponenty badania NIE JEST SZUMEM I NIE POWINNO BYĆ USUWANE.
    7. FORMATOWANIE DAT I WYMIARÓW:
        - Wymiary zapisuj w formacie cyfrowym z symbolem 'x', np.: "2 x 1,5 x 3 cm" (zamiast "dwa na jeden i pół na trzy").
        - Zadbaj o poprawną kapitalizację akronimów medycznych.
    8. NIE ZAŁĄCZAJ DANYCH OSOBOWYCH I PESELU: Pomiń dane osobowe pacjenta w oraz numer PESEL w poprawionej transkrypcji.
    9. NIE POMIJAJ ŻADNYCH SZCZEGÓŁÓW DOTYCZĄCYCH KOMPONENTÓW BADANIA, PROCEDURY MEDYCZNEJ LUB INFORMACJI MAKROSKOPOWYCH, np. informacji o oznaczeniach komponentów badania odpowiednim tuszem.

    ## Kontekst pomocniczy
    Aby ułatwić Ci zadanie, otrzymujesz poniżej wyekstraktowane jednostki (NER) - które przedstawiają kluczowe komponenty badania, np. organy i zmiany. Traktuj je jako drogowskaz i upewnij się, że nie zmieniasz przypisanych do nich faktów.

    <NER_EXTRACTION>
        %s
    </NER_EXTRACTION>

    Oto przykłady poprawnych transkrypcji. Użyj ich jako wzoru dla docelowego formatu, stylu i struktury wypowiedzi medycznej. NIE kopiuj z nich konkretnych danych.

    <TRANSCRIPTION_EXAMPLES>
        %s
    </TRANSCRIPTION_EXAMPLES>

    ## Twoje zadanie
    Przeanalizuj zaszumioną transkrypcję i wygeneruj WYŁĄCZNIE poprawiony, wolny od błędów fonetycznych, czysty tekst raportu medycznego, bez zbędnego formatowania. Nie dołączaj żadnych wstępów, komentarzy ani wyjaśnień.
    """


class NoFillAnswerer(Answerer):
    def __init__(self, model: str):
        self.model = model


    def correct_transcription(self, transcript, templates, ner_extraction):
        client = get_llm_client()
        prompt = PROMPT % (ner_extraction.model_dump(), templates)

        logger.info("ANSWERER: Wysyłanie requesta do poprawienia transkrypcji...")

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript},
            ],
            temperature=0.0
        )

        logger.info("ANSWERER: Otrzymano poprawioną transkrypcję.")

        text = response.choices[0].message.content
        return text