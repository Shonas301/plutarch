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

logger = logging.getLogger(__name__)

DOMAIN = os.getenv("YT_DOMAIN")
FFMPEG = os.getenv("FFMPEG")
OPUS_LOC = os.getenv("OPUS") 

discord.opus.load_opus(OPUS_LOC)


class YoutubePlayer(commands.Cog):
    def __init__(self, client):
        logger.info("Initializing recording commands")

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
        if url_portions.netloc != DOMAIN:
            await ctx.send("The link is not a youtube link", ephemeral=True)
            return
        await ctx.send(f"Playing {youtube_url}")
        _, source = search(youtube_url)
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


def search(query):
    with YoutubeDL({"format": "bestaudio", "noplaylist": "True"}) as ydl:
        try:
            requests.get(query)
        except:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
        else:
            info = ydl.extract_info(query, download=False)
    return (info, info["formats"][0]["url"])
