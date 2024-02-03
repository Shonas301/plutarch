from datetime import datetime

import discord
import pytz
from dicord.ext import commands


class RecordAudio(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.connections = {}

    @commands.command(name="record")
    async def record(self, ctx):
        channel = ctx.author.voice

        time = datetime.now(pytz.eastern)

        if channel is None:
            await ctx.respond("You're not in a voice chat", ephemeral=True)
        else:
            voice = await channel.channel.connect()
            self.connections.update({ctx.guild.id: {"voice": voice, "recording": True}})

            file_name = (
                ctx.author.display_name
                + "-"
                + ctx.author.discriminator
                + "-"
                + time.strftime("%m/%d/%Y")
            )

            voice.start_recording(
                discord.sinks.MP3Sink(),
                lambda _: (),  # add once_done
                ctx.author,
                file_name,
            )

            await ctx.respond("Recording has started", ephemeral=True)
