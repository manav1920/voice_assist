import os
import time
import traceback

from app.recorder import Recorder
from app.whisper_service import WhisperService
from app.gemini_service import GeminiService
from app.conversation_manager import ConversationManager
from app.text_preprocessor import TextPreprocessor
from app.xtts_service import XTTSService


def main():

    print("=" * 60)
    print("                  MANASVI AI")
    print("=" * 60)

    os.makedirs("recordings", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    print("\nLoading AI Modules...\n")

    recorder = Recorder()
    whisper = WhisperService()
    gemini = GeminiService()
    conversation = ConversationManager()
    preprocessor = TextPreprocessor()
    xtts = XTTSService()

    print("\nAll modules loaded successfully!")

    while True:

        input("\nPress ENTER to start recording...")

        total_start = time.perf_counter()

        try:

            # ---------------------------------
            # Recording
            # ---------------------------------

            start = time.perf_counter()

            recorder.record()

            recorder.save("recordings/input.wav")

            recording_time = time.perf_counter() - start

            # ---------------------------------
            # Whisper
            # ---------------------------------

            start = time.perf_counter()

            print("\nTranscribing...\n")

            user_text = whisper.transcribe(
                "recordings/input.wav"
            )

            whisper_time = time.perf_counter() - start

            print(f"\nYou : {user_text}")

            if not user_text.strip():

                print("\nNo speech detected.\n")
                continue

            if user_text.lower() in [
                "exit",
                "quit",
                "goodbye"
            ]:

                print("\nGoodbye!")
                break

            # ---------------------------------
            # Conversation History
            # ---------------------------------

            history = conversation.get_formatted_history()

            # ---------------------------------
            # Gemini
            # ---------------------------------

            start = time.perf_counter()

            assistant_reply = gemini.generate(
                user_message=user_text,
                history=history
            )

            gemini_time = time.perf_counter() - start

            conversation.add_user_message(user_text)
            conversation.add_assistant_message(assistant_reply)

            print("\nManasvi:\n")
            print(assistant_reply)

            # ---------------------------------
            # Text Preprocessor
            # ---------------------------------

            start = time.perf_counter()

            processed_text = preprocessor.preprocess(
                assistant_reply
            )

            preprocess_time = time.perf_counter() - start

            # ---------------------------------
            # XTTS
            # ---------------------------------

            start = time.perf_counter()

            print("\nGenerating voice...\n")

            xtts.text_to_speech(
                text=processed_text,
                speaker_wav="samples/voice.wav",
                output_file="output/response.wav",
                language="en"
            )

            xtts_time = time.perf_counter() - start

            print("\nVoice generated successfully!")
            print("Saved to output/response.wav")

            # ---------------------------------
            # Performance
            # ---------------------------------

            total_time = time.perf_counter() - total_start

            print("\n" + "=" * 60)
            print("            PERFORMANCE REPORT")
            print("=" * 60)
            print(f"Recording      : {recording_time:.2f} sec")
            print(f"Whisper        : {whisper_time:.2f} sec")
            print(f"Gemini         : {gemini_time:.2f} sec")
            print(f"Preprocessor   : {preprocess_time:.2f} sec")
            print(f"XTTS           : {xtts_time:.2f} sec")
            print("-" * 60)
            print(f"TOTAL          : {total_time:.2f} sec")
            print("=" * 60)

        except KeyboardInterrupt:

            print("\n\nStopping Manasvi...")
            break

        except Exception:

            print("\n" + "=" * 60)
            print("ERROR")
            print("=" * 60)

            traceback.print_exc()

            print("=" * 60)


if __name__ == "__main__":
    main()