from .mloader_base import TextToTextModel
# import openai
from openai import OpenAI
import json
from dotenv import load_dotenv
import os

from app_stt.config import TTT_PROMPT

class OpenAIGPT(TextToTextModel):
    def __init__(self):
        self.api_key = None
        self.client = None
        self.tokenizer = True
        self.model_version = "gpt-4o-2024-05-13"
        self.model_name = "OpenAI"

        self.load_model()

    def load_model(self):
        print("🔌 Łączenie z API OpenAI...")
        load_dotenv()
        self.api_key = os.getenv('OPENAI_KEY')
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1",
                        api_key=self.api_key  # ← Użyj zmiennej
                        )
        return self.client

    def load_tokenizer(self):
        # OpenAI API nie wymaga tokenizerów lokalnych
        self.tokenizer = True
        return True

    def make_out_of_the_box_adjusting(self, text: str) -> str:
        """
        Adjust the text from a medical transcript by extracting patient data into JSON.
        """

        system_prompt = (
            "Jesteś asystentem lekarza diagnosty, badającego wycinki organów i tkanek w zakładzie patomorfologii. "
            "Dokonujesz analizy kontekstualnej transkrypcji stworzonej przez model Whisper. "
            "W wyniku analizy powinny zostać usunięte fragmenty niezwiązane bezpośrednio z danymi pacjenta lub opisem próbki. "
            "Zakłócenia jak rozmowy osób trzecich lub hałas powinny być pominięte. "
            "Dodatkowo popraw gramatykę, ortografię i redakcję tekstu, nie zmieniając słownictwa (bez synonimów)."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_version,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": TTT_PROMPT.format(TRANSCRIPTION=text)},
                ],
                temperature=0.0
            )

            reply = response.choices[0].message.content
            cleaned_reply = reply.strip().strip("```json").strip("```").strip()

            try:
                json_data = json.loads(cleaned_reply)
                dumped = json.dumps(json_data, indent=4, ensure_ascii=False)
                return dumped
            except json.JSONDecodeError:
                print("❌ Nie udało się sparsować JSON. Odpowiedź modelu:")
                print(reply)
                return reply  # Zamiast rekursji, zwróć surową odpowiedź

        except Exception as e:
            print(f"❌ Błąd API: {e}")
            return "{}"
