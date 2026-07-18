import torch
from silero_vad import load_silero_vad, get_speech_timestamps


class VADService:

    def __init__(self):

        print("Loading Silero VAD...")

        self.model = load_silero_vad()

        print("Silero VAD Loaded Successfully!")

    def detect(self, audio):

        timestamps = get_speech_timestamps(
            audio,
            self.model,
            sampling_rate=16000
        )

        return timestamps