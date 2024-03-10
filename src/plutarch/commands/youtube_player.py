import asyncio
import logging
import subprocess
import os
from datetime import datetime
from urllib.parse import urlparse

import discord
import pytz
import requests
from discord.ext import commands
from youtube_dl import YoutubeDL
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()
YT_DOMAIN = os.getenv("YT_DOMAIN")
# SOUNDCLOUD_DOMAIN = os.getenv("SOUNDCLOUD_DOMAIN")
SOUNDCLOUD_DOMAIN = "soundcloud.com"
FFMPEG = os.getenv("FFMPEG")
OPUS_LOC = os.getenv("OPUS")

# opus = ctypes.util.
# discord.opus.load_opus(OPUS_LOC)
discord.opus._load_default()


class AudioLinkPlayer(commands.Cog):
    def __init__(self, client):
        logger.info("Initializing recording commands")
        self.queue = {}

    @commands.command(name="play")
    async def play(self, ctx, youtube_url):
        channel = ctx.author.voice
        FFMPEG_OPTS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn",
        }

        if channel is None:
            await ctx.send("You're not in a voice chat", ephemeral=True)
            return
        url_portions = urlparse(youtube_url)
        print(url_portions)
        if url_portions.netloc == YT_DOMAIN:
            _, source = search_youtube(youtube_url)
        elif url_portions.netloc == SOUNDCLOUD_DOMAIN:
            _, source = search_soundcloud(youtube_url)
        else:
            await ctx.send("The link is not a youtube link", ephemeral=True)
            return
        await ctx.send(f"Playing {youtube_url}")
        self.queue[channel] += youtube_url
        voice = await channel.channel.connect()
        voice.play(
            discord.FFmpegPCMAudio(source, executable=FFMPEG, **FFMPEG_OPTS),
            after=lambda e: print("done", e),
        )
        while voice.is_playing():
            await asyncio.sleep(1)
        await voice.disconnect()

    @commands.Cog.listener()
    async def on_voice_state_update(*_, **__):
        return


def search_youtube(query):
    with YoutubeDL({"format": "bestaudio", "noplaylist": "True"}) as ydl:
        try:
            requests.get(query)
        except:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
        else:
            info = ydl.extract_info(query, download=False)
    return (info, info["formats"][0]["url"])


def search_soundcloud(query):
    with YoutubeDL() as ydl:
        requests.get(query)
        info = ydl.extract_info(query, download=False)
        return (info, info["formats"][0]["url"])
