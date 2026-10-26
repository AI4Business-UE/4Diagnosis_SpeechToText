from ninja import NinjaAPI
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from .models import Keyword
from .schema import KeywordOut, KeywordIn


api = NinjaAPI(urls_namespace="keyword")


@api.get("/keyword/list", response=list[KeywordOut])
def list(request):
    return Keyword.objects.all()


@api.post("/keyword/create", response={201: KeywordOut})
def create(request, payload: KeywordIn):
    if Keyword.objects.count() >= 200:
        raise ValidationError("Limit 200 słów kluczowych został osiągnięty.")

    keyword = Keyword(text=payload.text)
    keyword.full_clean()
    keyword.save()

    return keyword


@api.delete("/keyword/delete/{keyword_id}", response={204: None})
def delete(request, keyword_id: int):
    keyword = get_object_or_404(
        Keyword.objects.all(),
        id = keyword_id
    )
    keyword.delete()

    return None


@api.exception_handler(ValidationError)
def validation_error(request, exc: ValidationError):
    if hasattr(exc, 'error_dict'):
        error_messages = exc.message_dict
    else:
        error_messages = {"__all__": exc.messages}

    return api.create_response(
        request,
        {"detail": error_messages},
        status=400
    )