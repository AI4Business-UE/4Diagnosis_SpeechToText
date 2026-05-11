from abc import ABC, abstractmethod
import torch

class TextToTextModel(ABC):

    @abstractmethod
    def load_model(self):
        pass

    @abstractmethod
    def load_tokenizer(self):
        pass

    @abstractmethod
    def make_out_of_the_box_adjusting(self, text: str) -> str:
        pass

    @staticmethod
    def get_device():
        try:
            # Check for accelerate first to avoid warnings
            try:
                import accelerate
                accelerate_available = True
            except ImportError:
                accelerate_available = False
                
            is_cuda_available = torch.cuda.is_available()
            print(f"CUDA dostępna: {is_cuda_available}")
            
            if is_cuda_available and accelerate_available:
                device = torch.device("cuda")
                print(f"Używam GPU: {torch.cuda.get_device_name(0)}")
            else:
                if is_cuda_available and not accelerate_available:
                    print("CUDA dostępna, ale pakiet accelerate nie jest dostępny. Używam CPU.")
                else:
                    print("CUDA niedostępna, używam CPU")
                device = torch.device("cpu")
            return device
        except Exception as e:
            print(f"Błąd przy wykrywaniu urządzenia: {str(e)}. Używam CPU.")
            return torch.device("cpu")
