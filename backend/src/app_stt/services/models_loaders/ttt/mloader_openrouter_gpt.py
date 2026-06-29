import json
import os
import requests
from .mloader_base import TextToTextModel
from app_stt.config import TTT_PROMPT
from logging_config import logger


class OpenRouterGPT(TextToTextModel):
    def __init__(self):
        self.model_version = "gpt-4o-2024-05-13"
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_KEY")
        if not self.api_key:
            logger.error("[TTT] OPENROUTER_API_KEY not set")

    def load_model(self):
        pass

    def load_tokenizer(self):
        pass

    def make_out_of_the_box_adjusting(self, text: str) -> str:
        if not self.api_key:
            logger.error("[TTT] No API key — returning original text")
            return text

        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": self.model_version,
                    "messages": [
                        {"role": "user", "content": TTT_PROMPT.format(TRANSCRIPTION=text)},
                    ],
                    "temperature": 0.0,
                }),
            )

            if response.status_code == 200:
                reply = response.json()["choices"][0]["message"]["content"]
                cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                try:
                    return json.dumps(json.loads(cleaned), indent=4, ensure_ascii=False)
                except json.JSONDecodeError:
                    logger.warning("[TTT] Response is not valid JSON, returning raw")
                    return reply
            else:
                logger.error(f"[TTT] OpenRouter error {response.status_code}: {response.text}")
                return "{}"

        except Exception as e:
            logger.error(f"[TTT] Request failed: {e}")
            return "{}"
