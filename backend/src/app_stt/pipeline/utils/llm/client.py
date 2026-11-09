"""Ścieżka kompatybilna dla surowego klienta.

Brama LLM (wybór Hosta, walidacja kluczy, kształtowanie żądań) mieszka w
`app_stt.pipeline.utils.llm.gateway`. Ten moduł zachowuje wyłącznie stare
ścieżki importu używane leniwie przez narzędzie eval — nowy kod produkcyjny
powinien importować wprost z `gateway`.
"""

from .gateway import (  # noqa: F401  (re-exporty kompatybilne)
    LLMGateway,
    active_host,
    get_gateway,
    is_configured,
    reset_gateway,
)


def get_llm_client() -> LLMGateway:
    """Zastąpione przez bramę — zwraca singletową instalację `LLMGateway`."""
    return get_gateway()
