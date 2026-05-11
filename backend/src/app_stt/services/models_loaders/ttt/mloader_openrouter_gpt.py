from .mloader_base import TextToTextModel
import requests
import json
from dotenv import load_dotenv
import os

from app_stt.config import TTT_PROMPT

class OpenRouterGPT(TextToTextModel):
    def __init__(self):
        self.api_key = None
        self.model_version = "gpt-4o-2024-05-13"
        self.model_name = "OpenRouterGPT"

        self.load_model()

    def load_model(self):
        print("🔌 Łączenie z API OpenRouter...")
        load_dotenv()
        self.api_key = os.getenv('OPENAI_KEY')  # Assuming same key
        return self.api_key

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
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": self.model_version,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": TTT_PROMPT.format(TRANSCRIPTION=text)},
                    ],
                    "temperature": 0.0
                })
            )

            if response.status_code == 200:
                result = response.json()
                reply = result["choices"][0]["message"]["content"]
                cleaned_reply = reply.strip().strip("```json").strip("```").strip()

                try:
                    json_data = json.loads(cleaned_reply)
                    dumped = json.dumps(json_data, indent=4, ensure_ascii=False)
                    return dumped
                except json.JSONDecodeError:
                    print("❌ Nie udało się sparsować JSON. Odpowiedź modelu:")
                    print(reply)
                    return reply  # Zamiast rekursji, zwróć surową odpowiedź
            else:
                print(f"❌ Błąd API: {response.status_code} - {response.text}")
                return "{}"

        except Exception as e:
            print(f"❌ Błąd API: {e}")
            return "{}"
