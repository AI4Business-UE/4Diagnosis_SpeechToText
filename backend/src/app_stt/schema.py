from ninja import ModelSchema

from .models import Keyword


class KeywordIn(ModelSchema):
    class Meta:
        model = Keyword
        fields = ["text"]


class KeywordOut(ModelSchema):
    class Meta:
        model = Keyword
        fields = ["id", "text"]