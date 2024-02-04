from .ready import ReadyConnection
from .record_audio import RecordAudio

cogs = [RecordAudio, ReadyConnection]

__all__ = ["cogs"]
