from django.db import models


class Keyword(models.Model):
    text = models.CharField(max_length=50, unique=True)