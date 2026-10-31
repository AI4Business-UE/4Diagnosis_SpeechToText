from ninja import NinjaAPI
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Keyword, KeywordCatalogMutex
from .schema import KeywordOut, KeywordIn


api = NinjaAPI(urls_namespace="keyword")


def _validated_keyword_text(text: str, *, exclude_id: int | None = None) -> str:
    text = text.strip()
    if not text:
        raise ValidationError({"text": "Hasło nie może być puste."})
    if len(text) > 50:
        raise ValidationError({"text": "Hasło może mieć maksymalnie 50 znaków."})
    if any(character in text for character in "<>\r\n"):
        raise ValidationError(
            {"text": "Hasło musi być zapisane w jednej linii i nie może zawierać znaków < ani >."}
        )

    duplicate_exists = any(
        keyword.id != exclude_id and keyword.text.casefold() == text.casefold()
        for keyword in Keyword.objects.all()
    )
    if duplicate_exists:
        raise ValidationError({"text": "Hasło o takiej nazwie już istnieje."})
    return text


def _polish_sort_key(text: str) -> tuple[int, ...]:
    alphabet = "aąbcćdeęfghijklłmnńoóprsśtuwyzźż"
    positions = {character: index for index, character in enumerate(alphabet)}
    return tuple(positions.get(character, len(alphabet) + ord(character)) for character in text.casefold())


def _lock_keyword_catalog() -> None:
    # Updating the singleton row acquires a write lock on SQLite as well as
    # row-level locks on databases that support SELECT ... FOR UPDATE.
    KeywordCatalogMutex.objects.filter(id=1).update(revision=F("revision") + 1)
    KeywordCatalogMutex.objects.select_for_update().get(id=1)


@api.get("/keyword/list", response=list[KeywordOut])
def list(request):
    return sorted(Keyword.objects.all(), key=lambda keyword: _polish_sort_key(keyword.text))


@api.post("/keyword/create", response={201: KeywordOut})
def create(request, payload: KeywordIn):
    with transaction.atomic():
        _lock_keyword_catalog()
        if Keyword.objects.count() >= 200:
            raise ValidationError("Limit 200 słów kluczowych został osiągnięty.")

        keyword = Keyword(text=_validated_keyword_text(payload.text))
        keyword.save()

    return keyword


@api.put("/keyword/update/{keyword_id}", response=KeywordOut)
def update(request, keyword_id: int, payload: KeywordIn):
    with transaction.atomic():
        _lock_keyword_catalog()
        keyword = get_object_or_404(Keyword.objects.all(), id=keyword_id)
        keyword.text = _validated_keyword_text(payload.text, exclude_id=keyword.id)
        keyword.save(update_fields=["text"])
    return keyword


@api.delete("/keyword/delete/{keyword_id}", response={204: None})
def delete(request, keyword_id: int):
    keyword = get_object_or_404(
        Keyword.objects.all(),
        id = keyword_id
    )
    keyword.delete()

    return None


@api.exception_handler(Http404)
def not_found_error(request, exc: Http404):
    return api.create_response(
        request,
        {"detail": "Nie znaleziono hasła o podanym identyfikatorze."},
        status=404,
    )


@api.exception_handler(ValidationError)
def validation_error(request, exc: ValidationError):
    if hasattr(exc, "error_dict"):
        error_messages = exc.message_dict
    else:
        error_messages = {"__all__": exc.messages}

    return api.create_response(
        request,
        {"detail": error_messages},
        status=400,
    )
