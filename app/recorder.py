import os
import threading

import sounddevice as sd
import soundfile as sf


class Recorder:

    def __init__(self):

        self.sample_rate = 16000
        self.channels = 1

        self.audio = []
        self.stream = None
        self.recording = False

    def callback(self, indata, frames, time, status):

        if self.recording:
            self.audio.append(indata.copy())

    def record(self):

        self.audio = []

        self.recording = True

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self.callback
        )

        self.stream.start()

        print("\nRecording...")
        print("Speak now...")
        print("Press ENTER again to stop recording.\n")

        input()

        self.recording = False

        self.stream.stop()
        self.stream.close()

        print("Recording Finished!\n")

    def save(self, filename="recordings/input.wav"):

        if len(self.audio) == 0:
            raise ValueError("No audio recorded.")

        os.makedirs("recordings", exist_ok=True)

        audio = self.audio[0]

        for chunk in self.audio[1:]:
            audio = __import__("numpy").vstack((audio, chunk))

        sf.write(
            filename,
            audio,
            self.sample_rate
        )

        print(f"Audio saved to {filename}")