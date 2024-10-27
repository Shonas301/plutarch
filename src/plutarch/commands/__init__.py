import yt_dlp as youtube_dl

from .audio_player import AudioLinkPlayer
from .ready import ReadyConnection

cogs = [ReadyConnection, AudioLinkPlayer]


__all__ = ["cogs"]
