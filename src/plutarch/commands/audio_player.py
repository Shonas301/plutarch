import asyncio
import logging
import os
from urllib.parse import urlparse

import aiohttp
import discord
from discord import Client, StageChannel, VoiceChannel
from discord.ext import commands, tasks
from yt_dlp import YoutubeDL

from .exceptions import AudioUrlError
from .state_interface import VoiceChannelCog, VoiceMeta
from .voice_connections import (
    ChannelState,
    ChannelStateManager,
    PlayerChannelState,
)

YT_DOMAIN = "www.youtube.com"
SOUNDCLOUD_DOMAIN = "soundcloud.com"
FFMPEG = os.getenv("FFMPEG")
OPUS_LOC = os.getenv("OPUS")
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
HTTP_OK = 200

discord.opus._load_default()

logger = logging.getLogger(__name__)


class AudioLinkPlayer(commands.Cog, VoiceChannelCog, metaclass=VoiceMeta):
    def __init__(self, client: Client, state_manager: ChannelStateManager):
        logger.info("Initializing audio player commands")
        self.join_active_cogs()
        self.enqueued: list[tuple[ChannelState, str]] = []
        self.play_queued.start()
        self._client = client
        self._state_manager = state_manager

    # Channel Agnostic Events
    async def cog_check(self, ctx):
        logger.debug("cog_check called")
        channel = ctx.author.voice
        if channel is None:
            await ctx.send("You are not currently in a voice channel")
            return False
        return True

    async def leave_voice_channel(self, channel: VoiceChannel | StageChannel) -> None:
        logger.debug("leave_voice_channel called")
        state = await self._state_manager.get(channel.id)
        if state is None or state.client is None:
            return
        state.client.stop()

    @tasks.loop(seconds=1)
    async def play_queued(self):
        logger.debug("play_queued called")
        vc_threads = []
        while self.enqueued:
            state, url = self.enqueued.pop()
            source = await get_source(url)
            vc_threads.append(self._play(state, source))
        await asyncio.gather(*vc_threads)

    # Commands
    @commands.command(name="play")
    async def play(self, ctx: commands.Context, url: str):
        logger.debug("play called")
        logger.info("user %s requested to play %s", ctx.author.name, url)
        channel = ctx.author.voice.channel

        # get or create channel state
        state = await self._state_manager.get(channel.id)
        if state is not None:
            if state.client is not None:
                logger.info("client already exists")
                if state.player is not None:
                    state.player.remain_connected = True
                state.client.stop_playing()
            else:
                await state.connect()
        else:
            state = await self._state_manager.get_or_create(channel.id, channel)
            state.player = PlayerChannelState()
            await state.connect()

        # ensure player state exists
        if state.player is None:
            state.player = PlayerChannelState()

        try:
            source = await get_source(url)
        except Exception:
            logger.exception("failed to resolve audio source for url: %s", url)
            await ctx.send(f"Could not get audio from that URL.")
            return

        state.player.playing = url
        await self._play(state, source)

    @commands.command(name="queue")
    async def queue(self, ctx: commands.Context, url: str):
        logger.debug("queue called")
        logger.info("user %s requested to queue %s", ctx.author.name, url)
        channel = ctx.author.voice.channel
        state = await self._state_manager.get(channel.id)
        if state is not None and state.player is not None:
            logger.info("plutarch is already playing in channel, adding to queue")
            state.player.queue.append(url)
            state.player.remain_connected = True
            return
        logger.info("No queue was found, playing in channel")
        await self.play(ctx, url)

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        logger.debug("stop called")
        channel = ctx.author.voice.channel
        channel_state = await self._state_manager.get(channel.id)
        if channel_state is None:
            await ctx.send("Nothing is currently playing.")
            return
        if channel_state.player is not None:
            channel_state.player.remain_connected = False
        if channel_state.client is not None:
            channel_state.client.stop_playing()

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        """Skips the currently playing song and plays the next one in the queue."""
        logger.debug("skip called")
        channel = ctx.author.voice.channel
        channel_state = await self._state_manager.get(channel.id)

        if (
            channel_state is None
            or channel_state.player is None
            or channel_state.client is None
        ):
            await ctx.send("Nothing is currently playing.")
            return

        if channel_state.client.is_playing():
            channel_state.client.stop_playing()

        if channel_state.player.queue:
            next_song = channel_state.player.queue[0]
            self.enqueued.append((channel_state, next_song))
            await ctx.send(f"Skipping to the next song: {next_song}")
        else:
            await ctx.send("No more songs in the queue.")
            await self._disconnect(channel_state)

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        logger.debug("pause called")
        await ctx.send("-- Not yet implemented --")

    # Connection actions
    async def _play(self, state: ChannelState, source):
        logger.debug("_play called")
        if state.client is None:
            logger.error("_play: state.client is None, cannot play")
            return

        playback_error: list[Exception | None] = [None]

        def _after(error: Exception | None) -> None:
            if error is not None:
                logger.error("playback error: %s", error)
            playback_error[0] = error

        try:
            state.client.play(
                discord.FFmpegPCMAudio(source, executable=FFMPEG, **FFMPEG_OPTS),
                after=_after,
            )
        except Exception:
            logger.exception("failed to start playback for source: %s", source)
            return

        # brief pause to let ffmpeg spin up before polling
        await asyncio.sleep(0.5)

        if state.client is not None and not state.client.is_playing():
            logger.error(
                "playback did not start — source: %s, ffmpeg: %s, error: %s",
                source,
                FFMPEG,
                playback_error[0],
            )
            return

        while state.client is not None and state.client.is_playing():
            await asyncio.sleep(1)

        if playback_error[0] is not None:
            logger.error("playback ended with error: %s", playback_error[0])

        # check if there are more songs in the queue
        if state.player is not None and len(state.player.queue) > 0:
            next_song = state.player.queue.pop(0)
            self.enqueued.append((state, next_song))
        elif state.player is None or not state.player.remain_connected:
            await self._disconnect(state)

    async def _disconnect(self, state: ChannelState):
        logger.debug("_disconnect called")
        logger.info("disconnecting audio player from server: %s", state.channel.name)
        if state.client is not None:
            await state.client.disconnect()
            state.client = None
        if state.player is not None:
            state.player.remain_connected = False
            state.player.queue = []


# Media helper functions
async def get_source(url: str):
    logger.debug("get_source called")
    url_portions = urlparse(url)
    if url_portions.netloc == YT_DOMAIN:
        _, source = await search_youtube(url)
    elif url_portions.netloc == SOUNDCLOUD_DOMAIN:
        _, source = await search_soundcloud(url)
    else:
        raise AudioUrlError("Not a valid url")
    return source


async def search_youtube(query):
    logger.debug("search_youtube called")
    async with aiohttp.ClientSession() as session:
        try:
            await _fetch_data(session, query)
        except AudioUrlError:
            info = await async_youtube_search(f"ytsearch:{query}")["entries"][0]
        else:
            info = await async_youtube_search(
                query,
            )
    return (info, info["url"])


async def search_soundcloud(query):
    with YoutubeDL() as ydl:
        info = ydl.extract_info(query, download=False)
        return (info, info["formats"][0]["url"])


async def _fetch_data(session: aiohttp.ClientSession, query: str):
    logger.debug("_fetch_data called")
    async with session.get(query) as response:
        if response.status != HTTP_OK:
            error_message = f"Failed to fetch data from {query}"
            raise AudioUrlError(error_message)
        return await response.read()


async def async_youtube_search(query: str):
    """Asynchronous YouTube search function."""
    logger.debug("async_youtube_search called")
    with YoutubeDL(
        {
            "format": "best/bestaudio",
            "noplaylist": "True",
        }
    ) as ydl:
        return await asyncio.to_thread(ydl.extract_info, query, download=False)
