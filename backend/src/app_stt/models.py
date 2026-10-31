from django.db import models


class Keyword(models.Model):
    text = models.CharField(max_length=50, unique=True)


class KeywordCatalogMutex(models.Model):
    """Database row used to serialize catalog writes across API requests."""

    id = models.PositiveSmallIntegerField(primary_key=True)
    revision = models.PositiveIntegerField(default=0)
