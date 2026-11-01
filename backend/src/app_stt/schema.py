from ninja import ModelSchema, Schema

from .models import Keyword


class KeywordIn(Schema):
    text: str


class KeywordOut(ModelSchema):
    class Meta:
        model = Keyword
        fields = ["id", "text"]
