from django.test import TestCase
from django.urls import reverse

from app_stt.models import Keyword


class KeywordManagementApiTests(TestCase):
    def test_create_trims_outer_whitespace_and_preserves_display_case(self):
        response = self.client.post(
            reverse("keyword:create"),
            {"text": "  Żółta Barwinka  "},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["text"], "Żółta Barwinka")

    def test_create_rejects_case_insensitive_duplicate(self):
        Keyword.objects.create(text="Żółciak")

        response = self.client.post(
            reverse("keyword:create"),
            {"text": "  żÓŁCIAK "},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("już istnieje", str(response.json()))

    def test_create_rejects_provider_unsupported_characters(self):
        response = self.client.post(
            reverse("keyword:create"),
            {"text": "rozpoznanie\nnowotworu"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("jednej linii", str(response.json()))

    def test_update_changes_keyword_text(self):
        keyword = Keyword.objects.create(text="Stara nazwa")

        response = self.client.put(
            reverse("keyword:update", kwargs={"keyword_id": keyword.id}),
            {"text": "  Nowa nazwa  "},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": keyword.id, "text": "Nowa nazwa"})
        self.assertEqual(Keyword.objects.get().text, "Nowa nazwa")

    def test_update_rejects_case_insensitive_duplicate_of_another_keyword(self):
        keyword = Keyword.objects.create(text="Własna nazwa")
        Keyword.objects.create(text="Żółciak")

        response = self.client.put(
            reverse("keyword:update", kwargs={"keyword_id": keyword.id}),
            {"text": "żÓŁCIAK"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("już istnieje", str(response.json()))

    def test_lists_keywords_in_polish_alphabetical_order(self):
        Keyword.objects.create(text="żaba")
        Keyword.objects.create(text="zebra")
        Keyword.objects.create(text="Łoś")

        response = self.client.get(reverse("keyword:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([keyword["text"] for keyword in response.json()], ["Łoś", "zebra", "żaba"])

    def test_update_returns_404_for_missing_keyword(self):
        response = self.client.put(
            reverse("keyword:update", kwargs={"keyword_id": 999}),
            {"text": "Nazwa"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("Nie znaleziono hasła", response.json()["detail"])
