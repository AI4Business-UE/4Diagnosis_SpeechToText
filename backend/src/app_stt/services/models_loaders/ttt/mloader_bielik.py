from .mloader_base import TextToTextModel
from ..utilities.out_of_the_box import OutOfTheBoxAdjuster

from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

from app_stt.config import TTT_PROMPT

class Bielik(TextToTextModel):

    def __init__(self):
        self.model_name: str = "speakleash/Bielik-7B-v0.1"
        self.device = self.get_device()
        self.tokenizer = self.load_tokenizer()
        self.model = self.load_model()

        self.prompt = TTT_PROMPT

    def load_model(self):
        print("🔄 BielikAi model loading...")
        try:

            """
            # Use BitsAndBytesConfig instead of load_in_8bit
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_threshold=6.0,
                llm_int8_has_fp16_weight=False
            )
            """
            quantization_config = None
            
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto",
                quantization_config=quantization_config,
            )
            return model
        except ValueError as e:
            if "requires `accelerate`" in str(e):
                print("Próba załadowania z alternatywnymi ustawieniami (bez accelerate)...")
                # Try without device_map and quantization
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    # No device_map or quantization
                )
                # Move model to the device manually
                model = model.to(self.device)
                print(f"Model załadowany na urządzenie: {self.device}")
                return model
            elif "bitsandbytes" in str(e):
                print("Próba załadowania bez kwantyzacji...")
                # Try without quantization
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    device_map="auto",
                )
                return model
            else:
                print(f"Nieznany błąd: {str(e)}")
                raise  # re-raise if it's a different ValueError

    def load_tokenizer(self):
        print("🔄 BielikAi tokenizer loading...")
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        return tokenizer

    def make_out_of_the_box_adjusting(self, text: str) -> str:
        print('Contextual adjustment in progress...')
        prompt_extended = self.prompt.format(TRANSCRIPTION=text)
        inputs = self.tokenizer(prompt_extended, return_tensors="pt").to(self.model.device)
        print("Tokeny:", inputs.input_ids[0].tolist())

        if 'token_type_ids' in inputs:
            inputs.pop('token_type_ids')

        outputs = self.model.generate(
            input_ids=inputs.input_ids,
            attention_mask=inputs.attention_mask,
            max_new_tokens=50,
            do_sample=False,
            num_beams=1,
            temperature=0.0001
        )

        output = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        print('Contextual adjustment done!')

        print(f"Oryginalne zdanie: {text}")
        print(f"Poprawione zdanie: {output}")
        return output






