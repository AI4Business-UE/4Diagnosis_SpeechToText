from django.core.management import call_command, CommandError
from django.test import TestCase

from app_stt.data.medical_keywords import MEDICAL_KEYWORDS
from app_stt.models import Keyword


class IndexKeywordsCommandTests(TestCase):
    def test_seeds_the_catalog_when_database_is_empty(self):
        call_command("index_keywords")

        self.assertEqual(Keyword.objects.count(), len(MEDICAL_KEYWORDS))

    def test_refuses_to_seed_when_catalog_already_has_entries(self):
        existing = Keyword.objects.create(text="Celowo usunięte hasła nie wracają")

        with self.assertRaises(CommandError):
            call_command("index_keywords")

        self.assertEqual(list(Keyword.objects.values_list("text", flat=True)), [existing.text])
