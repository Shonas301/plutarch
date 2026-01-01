from asyncio import Lock
from dataclasses import dataclass, field

import discord
from discord.ext import voice_recv


@dataclass
class PlayerChannelState:
    """state for audio playback in a voice channel."""

    queue: list[str] = field(default_factory=list)
    playing: str = ""
    remain_connected: bool = False


@dataclass
class RecorderChannelState:
    """state for recording audio in a voice channel."""

    file_names: dict[str, str] = field(default_factory=dict)


@dataclass
class ChannelState:
    """state for a voice channel connection."""

    channel: discord.VoiceChannel
    client: voice_recv.VoiceRecvClient | None = None
    player: PlayerChannelState | None = None
    recorder: RecorderChannelState | None = None

    async def connect(self, *_) -> voice_recv.VoiceRecvClient | None:
        """Connect to the voice channel if not already connected."""
        if self.client:
            return self.client
        if not self.channel:
            return None
        self.client = await self.channel.connect(cls=voice_recv.VoiceRecvClient)
        return self.client


class ChannelStateManager:
    """thread-safe manager for voice channel states.

    provides async-safe access to channel states with proper locking
    to prevent race conditions when multiple coroutines access state.
    """

    def __init__(self) -> None:
        self._channels: dict[int, ChannelState] = {}
        self._lock = Lock()

    async def get(self, channel_id: int) -> ChannelState | None:
        """Get the state for a channel, or None if not found."""
        async with self._lock:
            return self._channels.get(channel_id)

    async def get_or_create(
        self,
        channel_id: int,
        channel: discord.VoiceChannel,
    ) -> ChannelState:
        """Get existing state or create new one for the channel."""
        async with self._lock:
            if channel_id not in self._channels:
                self._channels[channel_id] = ChannelState(channel=channel)
            return self._channels[channel_id]

    async def remove(self, channel_id: int) -> ChannelState | None:
        """Remove and return the state for a channel."""
        async with self._lock:
            return self._channels.pop(channel_id, None)

    async def set(self, channel_id: int, state: ChannelState) -> None:
        """Set the state for a channel."""
        async with self._lock:
            self._channels[channel_id] = state

    async def contains(self, channel_id: int) -> bool:
        """Check if a channel exists in the manager."""
        async with self._lock:
            return channel_id in self._channels

    async def all_channel_ids(self) -> list[int]:
        """Get all channel IDs in the manager."""
        async with self._lock:
            return list(self._channels.keys())


# deprecated: use ChannelStateManager instead
_CHANNELS: dict[int, ChannelState] = {}


def get_channels() -> dict[int, ChannelState]:
    """deprecated: returns the global channels dict.

    use ChannelStateManager for thread-safe access.
    """
    return _CHANNELS


__all__ = [
    "ChannelState",
    "ChannelStateManager",
    "PlayerChannelState",
    "RecorderChannelState",
    "get_channels",
]
