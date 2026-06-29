import json
import os
from openai import OpenAI
from .mloader_base import TextToTextModel
from app_stt.config import TTT_PROMPT
from logging_config import logger


class OpenAIGPT(TextToTextModel):
    def __init__(self):
        self.model_version = "gpt-4o-2024-05-13"
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
        if not api_key:
            logger.error("[TTT] OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)

    def load_model(self):
        pass

    def load_tokenizer(self):
        pass

    def make_out_of_the_box_adjusting(self, text: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_version,
                messages=[{"role": "user", "content": TTT_PROMPT.format(TRANSCRIPTION=text)}],
                temperature=0.0,
            )
            reply = response.choices[0].message.content
            cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            try:
                return json.dumps(json.loads(cleaned), indent=4, ensure_ascii=False)
            except json.JSONDecodeError:
                logger.warning("[TTT] Response is not valid JSON, returning raw")
                return reply
        except Exception as e:
            logger.error(f"[TTT] OpenAI request failed: {e}")
            return "{}"
