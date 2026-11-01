from django.test import TestCase
from django.urls import reverse

from app_stt.models import Keyword


class KeywordListApiTests(TestCase):
    def test_returns_all_keywords(self):
        key1 = Keyword.objects.create(text="keyword1")
        key2 = Keyword.objects.create(text="keyword2")

        response = self.client.get(reverse("keyword:list"))

        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 2)

        for keyword in body:
            self.assertIn("id", keyword)
            self.assertIn("text", keyword)

        self.assertEqual(key1.id, body[0]['id'])
        self.assertEqual(key2.id, body[1]['id'])
