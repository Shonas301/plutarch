# from .record_audio import RecordAudio
from .audio_player import AudioLinkPlayer
from .ready import ReadyConnection

# cogs = [RecordAudio, ReadyConnection, AudioLinkPlayer]
cogs = [ReadyConnection, AudioLinkPlayer]

__all__ = ["cogs"]
