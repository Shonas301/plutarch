import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import discord
import requests
from discord import Client, StageChannel, VoiceChannel, VoiceClient
from discord.ext import commands, tasks
from dotenv import load_dotenv
from youtube_dl import YoutubeDL

from plutarch.commands.exceptions import AudioUrlError

from .state_interface import VoiceChannelCog, VoiceMeta

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

load_dotenv()
YT_DOMAIN = "www.youtube.com"
SOUNDCLOUD_DOMAIN = "soundcloud.com"
FFMPEG = os.getenv("FFMPEG")
OPUS_LOC = os.getenv("OPUS")
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

discord.opus._load_default()


@dataclass
class ChannelState:
    channel: VoiceChannel
    queue: list[str] = field(default_factory=list)
    playing: str = ""
    remain_connected: bool = False
    client: VoiceClient | None = None


class AudioLinkPlayer(commands.Cog, VoiceChannelCog, metaclass=VoiceMeta):
    def __init__(self, client: Client):
        logger.info("Initializing recording commands")
        self.join_active_cogs()
        self.channels_info: Mapping[int, ChannelState] = {}
        self.enqueued: list[tuple[ChannelState, str]] = []
        self.play_queued.start()
        self._client = client

    # Channel Agnostic Events
    async def cog_check(self, ctx):
        channel = ctx.author.voice
        if channel is None:
            await ctx.send("You are not currently in a voice channel")
            return False
        return True

    async def leave_voice_channel(self, channel: VoiceChannel | StageChannel) -> None:
        client = self.channels_info[channel.id].client
        if client is None:
            return
        client.stop()

    @tasks.loop(seconds=1)
    async def play_queued(self):
        vc_threads = []
        while self.enqueued:
            state, url = self.enqueued.pop()
            source = await get_source(url)
            vc_threads.append(self._play(state, source))
        asyncio.gather(*vc_threads)

    # Commands
    @commands.command(name="play")
    async def play(self, ctx: commands.Context, url: str):
        channel = ctx.author.voice.channel
        if channel.id in self.channels_info:
            state = self.channels_info[channel.id]
            if state.client is not None:
                state.remain_connected = True
                state.client.stop()
        else:
            state = ChannelState(channel)
            self.channels_info[channel.id] = state

        source = await get_source(url)
        state.playing = url
        await self._play(state, source)

    @commands.command(name="queue")
    async def queue(self, ctx, url):
        channel = ctx.author.voice.channel
        state = self.channels_info.get(channel.id)
        if state:
            state.queue.append(url)
            state.remain_connected = True
        else:
            await self.play(ctx, url)

    @commands.command(name="stop")
    async def stop(self, ctx):
        channel = ctx.author.voice.channel
        channel_state = self.channels_info[channel.id]
        channel_state.remain_connected = False
        if channel_state.client:
            channel_state.client.stop()

    # Connection actions
    async def _play(self, state, source):
        state.client = state.client if state.client else await state.channel.connect()

        state.client.play(
            discord.FFmpegPCMAudio(source, executable=FFMPEG, **FFMPEG_OPTS),
            after=lambda e: print("done", e),
        )
        while state.client.is_playing():
            await asyncio.sleep(1)
        if not state.remain_connected:
            await self._disconnect(state)
        if not len(state.queue):
            await self._disconnect(state)
        else:
            next_song = state.queue.pop(0)
            self.enqueued.append((state, next_song))

    async def _disconnect(self, state):
        await state.client.disconnect()
        state.remain_connected = False
        state.client = None
        self.queue = []


# Media helper functions
async def get_source(url):
    url_portions = urlparse(url)
    if url_portions.netloc == YT_DOMAIN:
        _, source = search_youtube(url)
    elif url_portions.netloc == SOUNDCLOUD_DOMAIN:
        _, source = search_soundcloud(url)
    else:
        raise AudioUrlError("Not a valid url")
    return source


def search_youtube(query):
    with YoutubeDL({"format": "bestaudio", "noplaylist": "True"}) as ydl:
        try:
            requests.get(query, timeout=30)
        except requests.exceptions.HTTPError:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
        else:
            info = ydl.extract_info(query, download=False)
    return (info, info["formats"][0]["url"])


def search_soundcloud(query):
    with YoutubeDL() as ydl:
        info = ydl.extract_info(query, download=False)
        return (info, info["formats"][0]["url"])
