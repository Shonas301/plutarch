from .ready import ReadyConnection
from .record_audio import RecordAudio
from .youtube_player import YoutubePlayer

cogs = [RecordAudio, ReadyConnection, YoutubePlayer]

__all__ = ["cogs"]
