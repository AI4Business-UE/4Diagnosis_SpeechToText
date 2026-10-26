from django.test import TestCase
from django.urls import reverse

from app_stt.models import Keyword


class KeywordDeleteApiTests(TestCase):
    def test_deletes_keyword(self):
        keyword = Keyword.objects.create(text="dummy")

        response = self.client.delete(
            reverse("keyword:delete", kwargs={"keyword_id": keyword.id})
        )

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(Keyword.objects.filter(id = keyword.id).first())


    def test_returns_404_if_not_found(self):
        response = self.client.delete(
            reverse("keyword:delete", kwargs={"keyword_id": 123})
        )

        self.assertEqual(response.status_code, 404)