from plutarch.arc.cog import ArcStash

from .audio_player import AudioLinkPlayer
from .ready import ReadyConnection

cogs = [ReadyConnection, AudioLinkPlayer, ArcStash]


__all__ = ["cogs"]
