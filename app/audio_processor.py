import numpy as np
import soundfile as sf


class AudioProcessor:

    def __init__(self, sample_rate=16000):

        self.sample_rate = sample_rate

        # Silence threshold
        self.silence_threshold = 0.02

        # Target peak after normalization
        self.target_peak = 0.95

    # -----------------------------
    # Normalize Volume
    # -----------------------------
    def normalize(self, audio):

        peak = np.max(np.abs(audio))

        if peak == 0:
            return audio

        audio = audio / peak

        audio *= self.target_peak

        return audio

    # -----------------------------
    # Remove Leading & Trailing Silence
    # -----------------------------
    def trim_silence(self, audio):

        if len(audio.shape) > 1:
            audio = audio.squeeze()

        indices = np.where(np.abs(audio) > self.silence_threshold)[0]

        if len(indices) == 0:
            return np.array([], dtype=np.float32)

        start = indices[0]
        end = indices[-1] + 1

        return audio[start:end]

    # -----------------------------
    # Check Empty Recording
    # -----------------------------
    def is_empty(self, audio):

        if len(audio) == 0:
            return True

        energy = np.mean(np.abs(audio))

        return energy < self.silence_threshold

    # -----------------------------
    # Recording Duration
    # -----------------------------
    def get_duration(self, audio):

        return len(audio) / self.sample_rate

    # -----------------------------
    # Audio Information
    # -----------------------------
    def get_audio_info(self, audio):

        return {

            "Duration (sec)": round(self.get_duration(audio), 2),

            "Peak": round(float(np.max(np.abs(audio))), 3),

            "Average Loudness": round(float(np.mean(np.abs(audio))), 3),

            "Sample Rate": self.sample_rate

        }

    # -----------------------------
    # Save WAV
    # -----------------------------
    def save(self, audio, filename):

        sf.write(
            filename,
            audio,
            self.sample_rate
        )

    # -----------------------------
    # Complete Pipeline
    # -----------------------------
    def process(self, audio):

        audio = self.normalize(audio)

        audio = self.trim_silence(audio)

        if self.is_empty(audio):

            raise ValueError("No speech detected.")

        return audio