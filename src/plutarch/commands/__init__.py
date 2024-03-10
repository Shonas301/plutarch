from .ready import ReadyConnection
# from .record_audio import RecordAudio
from .youtube_player import AudioLinkPlayer

# cogs = [RecordAudio, ReadyConnection, AudioLinkPlayer]
cogs = [ReadyConnection, AudioLinkPlayer]

__all__ = ["cogs"]
