import logging
from datetime import datetime

import discord
import pytz
from discord.ext import commands, voice_recv

logger = logging.getLogger(__name__)
discord.opus._load_default()


class RecordAudio(commands.Cog):
    def __init__(self, client):
        logger.info("Initializing recording commands")
        self.client = client
        self.connections = {}
        self.file_names = {}

    @commands.command(name="record")
    async def record(self, ctx):
        channel = ctx.author.voice

        time = datetime.now(pytz.utc)

        if channel is None:
            await ctx.send("You're not in a voice chat", ephemeral=True)
            return
        else:
            await ctx.send("starting VC recording session")
            voice = await channel.channel.connect(cls=voice_recv.VoiceRecvClient)
            for member in channel.channel.members:
                print(member.display_name)
                if member.display_name == "plutarch":
                    continue
                logger.info("%s", str(dir(voice)))
                self.connections.update(
                    {ctx.guild.id: {"voice": voice, "recording": True}}
                )

                base_file_name = (
                    member.display_name
                    + f"{time.day}_{time.hour}_{time.second}"
                    + ".wav"
                )
                # file_name = str((Path.cwd() / base_file_name).absolute())
                self.file_names[member.display_name] = base_file_name
                logger.info("file name: %s", base_file_name)

                voice.listen(voice_recv.WaveSink(destination=base_file_name))

    @commands.command(name="stop")
    async def stop(self, ctx):
        await ctx.send("Disconnecting")
        await ctx.voice_client.disconnect()

    #     # results = [
    #     #     f"{author}: {wav_to_text(file_name)}"
    #     #     for author, file_name in self.file_names.items()
    #     # ]
    #     results = [
    #         wav_to_text(str(file_name)) for file_name in self.file_names.values()
    #     ]
    #     await asyncio.gather(*results)
    #     await ctx.send(results)

    # @commands.Cog.listener()
    # async def on_voice_state_update(
    #     self,
    #     member: discord.Member,
    #     before: discord.VoiceState,
    #     after: discord.VoiceState,
    # ):
    #     if before.channel is None and after.channel is not None:
    #         return

    #     file_name = self.file_names.pop(member.display_name, None)
    #     if file_name is None:
    #         return

    #     result = await(wav_to_text(file_name))
    #     await member.send(result)
