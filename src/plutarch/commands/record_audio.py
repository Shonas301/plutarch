import logging
from datetime import datetime

import discord
import pytz
from discord.ext import commands, voice_recv

logger = logging.getLogger(__name__)


class RecordAudio(commands.Cog):
    def __init__(self, client):
        logger.info("Initializing recording commands")
        self.client = client
        self.connections = {}

    @commands.command(name="record")
    async def record(self, ctx):
        channel = ctx.author.voice

        time = datetime.now(pytz.utc)

        voice = await channel.channel.connect(cls=voice_recv.VoiceRecvClient)
        if channel is None:
            await ctx.send("You're not in a voice chat", ephemeral=True)
        else:
            voice = await channel.channel.connect()
            logger.info("%s", str(dir(voice)))
            self.connections.update({ctx.guild.id: {"voice": voice, "recording": True}})

            file_name = (
                ctx.author.display_name
                + "-"
                + ctx.author.discriminator
                + "-"
                + time.strftime("%m/%d/%Y")
            )
            logger.info("file name: %s", file_name)


            await ctx.send("Recording has started", ephemeral=True)
