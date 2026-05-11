from app_stt.config import TTT_MODEL, TTT_PROMPT
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

class OutOfTheBoxAdjuster:
    def __init__(self, model, tokenizer):
        self.device = self.get_device()
        self.prompt = TTT_PROMPT
        self.tokenizer = tokenizer
        self.model = model

    @staticmethod
    def get_device():
      print(torch.cuda.is_available())  # Powinno zwrócić True jeśli CUDA jest dostępna
      if torch.cuda.is_available():
          device = torch.device("cuda")
          print(f"Używam GPU: {torch.cuda.get_device_name(0)}")
      else:
          device = torch.device("cpu")
          print("CUDA niedostępna, używam CPU")
      return device

    @staticmethod
    def load_tokenizer(model_name):
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        return tokenizer

    @staticmethod
    def load_model(model_name):
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            load_in_8bit=True,
        )
        return model

    def make_out_of_the_box_adjusting(self, text: str) -> str:
      prompt_extended = self.prompt.format(text)
      print(prompt_extended[:100])
      inputs = self.tokenizer(prompt_extended, return_tensors="pt").to(self.model.device)
      print("Tokeny:", inputs.input_ids[0].tolist()[:20])

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

      print(f"Oryginalne zdanie: {text}")
      print(f"Poprawione zdanie: {output}")
        
      return output