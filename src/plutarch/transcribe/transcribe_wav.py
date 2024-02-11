import os
from pathlib import Path

import whisper

MODEL = whisper.load_model(os.getenv("WHISPER_MODEL", "base"))


async def wav_to_text(file_name: str | Path):
    result = MODEL.transcribe(file_name)
    return result["text"]
