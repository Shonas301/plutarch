from asyncio import Semaphore
from collections.abc import Mapping
from dataclasses import dataclass, field

import discord
from discord.ext import voice_recv


@dataclass
class PlayerChannelState:
    queue: list[str] = field(default_factory=list)
    playing: str = ""
    remain_connected: bool = False


@dataclass
class RecorderChannelState:
    file_names: Mapping[str, str] = field(default_factory=list)


@dataclass
class ChannelState:
    channel: discord.VoiceChannel
    client: voice_recv.VoiceRecvClient | None = None
    num_connections: int = 0
    player: PlayerChannelState | None = None
    recorder: RecorderChannelState | None = None

    async def connect(self, *_) -> voice_recv.VoiceRecvClient:
        if self.client:
            return self.client
        if not self.channel:
            return None
        self.client = await self.channel.connect(cls=voice_recv.VoiceRecvClient)
        return self.client


CHANNELS: Mapping[str, ChannelState] = {}
lock = Semaphore()


def get_channels():
    return CHANNELS


__all__ = ["ChannelState", "PlayerChannelState", "RecorderChannelState", "get_channels"]
