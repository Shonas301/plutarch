import asyncio
import logging
import os
from urllib.parse import urlparse

import discord
import requests
from discord import Client, StageChannel, VoiceChannel
from discord.ext import commands, tasks
from dotenv import load_dotenv
from yt_dlp import YoutubeDL

from plutarch.commands.exceptions import AudioUrlError
from plutarch.commands.voice_connections import (
    ChannelState,
    PlayerChannelState,
    get_channels,
)

from .state_interface import VoiceChannelCog, VoiceMeta

lock = asyncio.Semaphore()

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


class AudioLinkPlayer(commands.Cog, VoiceChannelCog, metaclass=VoiceMeta):
    def __init__(self, client: Client):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing recording commands")
        self.join_active_cogs()
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
        async with get_channels() as channels_info:
            client = channels_info[channel.id].client
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
    async def play(self, ctx: commands.Context, *url_input):
        self.logger.info("user %s requested to play %s", ctx.author.name, url_input)
        url = url_input[0]
        channel = ctx.author.voice.channel
        player_state: PlayerChannelState
        channels_info = get_channels()
        self.logger.info("found channels: %s", channels_info)
        if channel.id in channels_info:
            state = channels_info[channel.id]
            if state.client is not None:
                self.logger.info("client already exists")
                state.player.remain_connected = True
                state.client.stop_playing()
                player_state = state.player
            else:
                await state.connect()
                player_state = state.player
        else:
            channels_info[channel.id] = state = ChannelState(channel)
            channels_info[channel.id].player = player_state = PlayerChannelState()
            await channels_info[channel.id].connect()

        source = await get_source(url)
        player_state.playing = url
        task = asyncio.create_task(self._play(state, source))
        asyncio.sleep(0)
        if len(url_input) > 1:
            await asyncio.gather(*[self.queue(ctx, url) for url in url_input[1:]])
        await task

    @commands.command(name="queue")
    async def queue(self, ctx: commands.Context, url: str):
        self.logger.info("user %s requested to queue %s", ctx.author.name, url)
        channel = ctx.author.voice.channel
        state: ChannelState | None = None
        channels_info = get_channels()
        state = channels_info[channel.id]
        if state.player:
            self.logger.info("plutarch is already playing in channel, adding to queue")
            state.player.queue.append(url)
            state.player.remain_connected = True
            return
        self.logger.info("No queue was found, playing in channel")
        await self.play(ctx, url)

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        channel = ctx.author.voice.channel
        channels_info = get_channels()
        channel_state = channels_info[channel.id]
        channel_state.player.remain_connected = False
        if channel_state.client:
            channel_state.client.stop_playing()

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        await ctx.send("-- Not yet implemented --")

    # Connection actions
    async def _play(self, state: ChannelState, source):
        state.client.play(
            discord.FFmpegPCMAudio(source, executable=FFMPEG, **FFMPEG_OPTS),
            after=lambda e: print("done", e),
        )
        while state.client.is_playing():
            await asyncio.sleep(1)
        if not state.player.remain_connected:
            await self._disconnect(state)
        if not len(state.player.queue):
            await self._disconnect(state)
        else:
            next_song = state.player.queue.pop(0)
            self.enqueued.append((state, next_song))

    async def _disconnect(self, state: ChannelState):
        self.logger.info(
            "disconnecting audio player from server: %s", state.channel.name
        )
        if state.client is not None:
            await state.client.disconnect()
            state.player.remain_connected = False
            state.client = None
            self.queue = []


# Media helper functions
async def get_source(url: str):
    url_portions = urlparse(url)
    if url_portions.netloc == YT_DOMAIN:
        _, source = search_youtube(url)
    elif url_portions.netloc == SOUNDCLOUD_DOMAIN:
        _, source = search_soundcloud(url)
    else:
        raise AudioUrlError("Not a valid url")
    return source


def search_youtube(query):
    with YoutubeDL({"format": "m4a/bestaudio/best", "noplaylist": "True"}) as ydl:
        try:
            requests.get(query, timeout=30)
        except requests.exceptions.HTTPError:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
        else:
            info = ydl.extract_info(query, download=False)
    return (info, info["url"])


def search_soundcloud(query):
    with YoutubeDL() as ydl:
        info = ydl.extract_info(query, download=False)
        return (info, info["formats"][0]["url"])
