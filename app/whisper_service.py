import torch
import whisper


class WhisperService:
    """
    Converts speech audio into text using OpenAI Whisper.
    """

    def __init__(self, model_name: str = "base"):

        print("\nLoading Whisper Model...")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"Using Device : {self.device.upper()}")

        self.model = whisper.load_model(
            model_name,
            device=self.device
        )

        print("Whisper Loaded Successfully!\n")

    def transcribe(self, audio_path: str) -> str:

        print("Transcribing Audio...")

        result = self.model.transcribe(
            audio_path,
            fp16=torch.cuda.is_available(),
            language="en",
            task="transcribe",
            temperature=0.0
        )
   
        text = result["text"].strip()

        print("Transcription Complete.\n")

        return text