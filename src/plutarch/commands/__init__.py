from .audio_player import AudioLinkPlayer
from .ready import ReadyConnection
from .record_audio import RecordAudio

cogs = [RecordAudio, ReadyConnection, AudioLinkPlayer]

__all__ = ["cogs"]
