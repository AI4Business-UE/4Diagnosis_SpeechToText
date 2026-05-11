from .mloader_base import TextToTextModel
from ..utilities.out_of_the_box import OutOfTheBoxAdjuster


class PLLuM(TextToTextModel):
    def load_model(self):
        print("Ładowanie Pllum...")
        model = OutOfTheBoxAdjuster.load_model("CYFRAGOVPL/Llama-PLLuM-8B-instruct")
        return model

    def load_tokenizer(self):
        tokenizer = OutOfTheBoxAdjuster.load_tokenizer("CYFRAGOVPL/Llama-PLLuM-8B-instruct")
        return tokenizer


