from faster_whisper import WhisperModel

print("Loading model...")

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)

print("Model loaded successfully!")