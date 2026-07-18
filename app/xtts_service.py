import torch
from TTS.api import TTS


class XTTSService:

    def __init__(self):

        print("Loading XTTS-v2 model...")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        
        self.tts = TTS(
    "tts_models/multilingual/multi-dataset/xtts_v2"
                      ).to(self.device)
        print("XTTS-v2 Loaded Successfully!")

    def text_to_speech(
        self,
        text,
        speaker_wav,
        output_file,
        language="en"
    ):

        self.tts.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=output_file
        )

        return output_file