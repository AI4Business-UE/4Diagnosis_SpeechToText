"""Domenowe zakresy sensowności rozmiaru preparatu/narządu.

TODO (do przeglądu przez osobę medyczną): wartości są WSTĘPNE i celowo hojne —
to górne granice sensownego wymiaru CAŁEGO narządu w cm, z dużym zapasem. Służą do
wychwytywania wyraźnego nonsensu (np. 40 cm nerka, "tkanka 7 metrów"), a nie do
precyzyjnej oceny. Dobierane tak, żeby minimalizować false-positive: preparaty bywają
powiększone patologicznie, więc lepiej flagować tylko rzeczy ewidentnie bezsensowne.
"""

# Górna granica sensownego wymiaru [cm] per narząd (forma kanoniczna).
ORGAN_MAX_DIMENSION_CM = {
    "nerka": 20.0,
    "macica": 25.0,
    "szyjka macicy": 10.0,
    "jajnik": 20.0,
    "jajowód": 15.0,
    # Resekaty jelita bywają bardzo długie (nawet >1 m) — limit celowo wysoki.
    "jelito cienkie": 200.0,
    "jelito grube": 200.0,
    "wątroba": 35.0,
    "płuco": 30.0,
    "tarczyca": 12.0,
    "prostata": 10.0,
    "pęcherz moczowy": 20.0,
    "pęcherzyk żółciowy": 15.0,
    "żołądek": 35.0,
    "przełyk": 40.0,
    "śledziona": 25.0,
    "węzeł chłonny": 10.0,
    "gruczoł piersiowy": 30.0,
    # Kości długie (np. udowa) bywają ~45 cm — limit z zapasem.
    "kość": 60.0,
    "skóra": 40.0,
}

# Fallback dla nieznanego / niepodanego narządu (zachowanie jak dotychczasowy globalny próg).
GLOBAL_MAX_DIMENSION_CM = 50.0

# Rdzeń (substring) -> forma kanoniczna. Tania obsługa polskiej fleksji.
# UWAGA: kolejność ma znaczenie — bardziej specyficzne (złożone) narządy MUSZĄ być wcześniej
# niż ogólne, żeby np. "szyjka macicy" nie rozwiązało się jako "macica",
# a "pęcherzyk żółciowy" nie jako "pęcherz moczowy". Dopasowanie: pierwszy pasujący wygrywa.
ORGAN_STEMS = [
    ("szyjk", "szyjka macicy"),
    ("pęcherzyk", "pęcherzyk żółciowy"),
    ("pęcherz", "pęcherz moczowy"),
    ("jelito cienk", "jelito cienkie"),
    ("jelito grub", "jelito grube"),
    ("jelit", "jelito grube"),
    ("węz", "węzeł chłonny"),
    ("pier", "gruczoł piersiowy"),
    ("nerk", "nerka"),
    ("macic", "macica"),
    ("jajnik", "jajnik"),
    ("jajow", "jajowód"),
    ("wątrob", "wątroba"),
    ("płuc", "płuco"),
    ("tarczyc", "tarczyca"),
    ("prostat", "prostata"),
    ("żołąd", "żołądek"),
    ("przełyk", "przełyk"),
    ("śledzion", "śledziona"),
    ("kość", "kość"),
    ("kośc", "kość"),
    ("kost", "kość"),
    ("skór", "skóra"),
]
