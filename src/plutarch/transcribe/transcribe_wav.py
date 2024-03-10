import asyncio
import functools
import os
from pathlib import Path
import typing

import whisper

MODEL = whisper.load_model(os.getenv("WHISPER_MODEL", "base"))

def to_thread(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        wrapped = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, wrapped)
    return wrapper


@to_thread
async def wav_to_text(file_name: str | Path):
    result = MODEL.transcribe(file_name)
    return result["text"]
