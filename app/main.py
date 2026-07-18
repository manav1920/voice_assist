from xtts_service import XTTSService
from text_preprocessor import TextPreprocessor

print("=" * 50)
print("AI Voice Assistant")
print("=" * 50)

tts = XTTSService()
preprocessor = TextPreprocessor()


raw_text = input("\nEnter text to speak: ")

processed_text = preprocessor.preprocess(raw_text)

print("\nProcessed Text:")
print(processed_text)

tts.text_to_speech(
    text=processed_text,
    speaker_wav="samples/voice.wav",
    output_file="output/response.wav",
    language="en"
)

print("\nVoice generated successfully!")
print("Saved to output/response.wav")