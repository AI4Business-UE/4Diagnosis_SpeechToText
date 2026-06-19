from .mloader_base import TextToTextModel
from ..utilities.out_of_the_box import OutOfTheBoxAdjuster
from app_stt.config import TTT_PROMPT
from logging_config import logger


class Bielik(TextToTextModel):
    def __init__(self):
        self.model_name = "speakleash/Bielik-7B-v0.1"
        self.device = self.get_device()
        self.tokenizer = self.load_tokenizer()
        self.model = self.load_model()

    def load_model(self):
        from transformers import AutoModelForCausalLM
        logger.info("[Bielik] Loading model...")
        try:
            model = AutoModelForCausalLM.from_pretrained(self.model_name, device_map="auto")
            logger.info("[Bielik] Model loaded")
            return model
        except ValueError as e:
            if "requires `accelerate`" in str(e) or "bitsandbytes" in str(e):
                logger.warning(f"[Bielik] Retrying without device_map: {e}")
                model = AutoModelForCausalLM.from_pretrained(self.model_name)
                return model.to(self.device)
            raise

    def load_tokenizer(self):
        from transformers import AutoTokenizer
        logger.info("[Bielik] Loading tokenizer...")
        return AutoTokenizer.from_pretrained(self.model_name)

    def make_out_of_the_box_adjusting(self, text: str) -> str:
        import torch
        prompt = TTT_PROMPT.format(TRANSCRIPTION=text)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        inputs.pop("token_type_ids", None)

        outputs = self.model.generate(
            input_ids=inputs.input_ids,
            attention_mask=inputs.attention_mask,
            max_new_tokens=50,
            do_sample=False,
            num_beams=1,
            temperature=0.0001,
        )
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.info(f"[Bielik] Corrected: {result[:80]}")
        return result
