import logging
from datetime import datetime

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

        if channel is None:
            await ctx.send("You're not in a voice chat", ephemeral=True)
        else:
            ctx.send("starting VC recording session")
            voice = await channel.channel.connect(cls=voice_recv.VoiceRecvClient)
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

            voice.listen(voice_recv.WaveSink(destination="test.wav"))

    @commands.command(name="stop")
    async def stop(self, ctx):
        await ctx.voice_client.disconnect()


def listen(user, data: voice_recv.VoiceData):
    print(f"Got packet from user {user}")
    print(f"{dir(data)!s}")
    print(f"{data}")
