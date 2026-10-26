from django.test import TestCase
from django.urls import reverse

from app_stt.models import Keyword


class KeywordCreateApiTests(TestCase):
    def test_creates_keyword(self):
        self.assertEqual(Keyword.objects.count(), 0)

        response = self.client.post(
            reverse("keyword:create"),
            data={
                "text": "Some keyword"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Keyword.objects.count(), 1)

        keyword = Keyword.objects.get()
        self.assertEqual(keyword.text, "Some keyword")


    def test_returns_400_if_non_unique_keyword(self):
        Keyword.objects.create(text="keyword")

        response = self.client.post(
            reverse("keyword:create"),
            {
                "text": "keyword"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json()['detail']

        self.assertIn("text", errors)
        self.assertIn("Keyword with this Text already exists.", errors["text"])


    def test_returns_400_if_empty_keyword(self):
        response = self.client.post(
            reverse("keyword:create"),
            {
                "text": ""
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json()['detail']

        self.assertIn("text", errors)
        self.assertIn("This field cannot be blank.", errors["text"])


    def test_returns_400_if_none_keyword(self):
        response = self.client.post(
            reverse("keyword:create"),
            {
                "text": None
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        errors = response.json()['detail']

        for error in errors:
            if 'text' in error['loc']:
                self.assertEqual("Input should be a valid string", error['msg'])


    def test_cannot_create_if_200_keywords_exist(self):
        for i in range(200):
            Keyword.objects.create(text=f"keyword-{i}")


        response = self.client.post(
            reverse("keyword:create"),
            { "text": "new-keyword" },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

        errors = response.json()['detail']
        self.assertIn("__all__", errors)
        self.assertIn("Limit 200 słów kluczowych został osiągnięty.", errors['__all__'])