# import asyncio
# import logging
# import os
# from datetime import datetime
# from typing import Dict, Optional

# import discord
# from discord.opus import Decoder as OpusDecoder
# import wave
# import pytz
# from discord.ext import commands, voice_recv
# from src.plutarch.transcribe.transcribe_wav import wav_to_text

# logger = logging.getLogger(__name__)
# # discord.opus.load_opus(os.getenv('OPUS'))
# discord.opus._load_default()

# class MultiWaveSink(voice_recv.AudioSink):
#     """Endpoint AudioSink that generates a wav file.
#     Best used in conjunction with a silence generating sink. (TBD)
#     """


#     CHANNELS = OpusDecoder.CHANNELS
#     SAMPLE_WIDTH = OpusDecoder.SAMPLE_SIZE // OpusDecoder.CHANNELS
#     SAMPLING_RATE = OpusDecoder.SAMPLING_RATE

#     def __init__(self, user_destinations: Dict[str, wave._File]):
#         super().__init__()

#         self._parent_file = wave.open(f"{' '.join(user_destinations.keys())}", "wb")
#         self._files: Dict[str, wave.Wave_write] = {}
#         for user_name, file_loc in user_destinations.items():
#             self._files[user_name] = wave.open(file_loc, 'wb')
#             self._files[user_name].setnchannels(self.CHANNELS)
#             self._files[user_name].setsampwidth(self.SAMPLE_WIDTH)
#             self._files[user_name].setframerate(self.SAMPLING_RATE)

#     def wants_opus(self) -> bool:
#         return False

#     def write(self, user: Optional[discord.User], data: voice_recv.VoiceData) -> None:
#         if self._files.get(user.display_name):
#             self._files[user.display_name].writeframes(data.pcm)
#         self._parent_file.writeframes(data.pcm)


# class RecordAudio(commands.Cog):
#     def __init__(self, client):
#         logger.info("Initializing recording commands")
#         self.client = client
#         self.connections = {}
#         self.file_names = {}

#     @commands.command(name="record")
#     async def record(self, ctx):
#         channel = ctx.author.voice

#         time = datetime.now(pytz.utc)

#         if channel is None:
#             await ctx.send("You're not in a voice chat", ephemeral=True)
#             return
#         else:
#             await ctx.send("starting VC recording session")
#             voice = await channel.channel.connect(cls=voice_recv.VoiceRecvClient)
#             user_destinations = {}
#             for member in channel.channel.members:
#                 if member.display_name == os.getenv('DISCORD_BOT_NAME'):
#                     continue
#                 print(member.display_name)
#                 if member.display_name == "plutarch":
#                     continue
#                 logger.info("%s", str(dir(voice)))
#                 self.connections.update(
#                     {ctx.guild.id: {"voice": voice, "recording": True}}
#                 )

#                 base_file_name = (
#                     member.display_name + f"{time.day}_{time.hour}_{time.second}" + ".wav"
#                 )
#                 self.file_names[member.display_name] = base_file_name
#                 user_destinations.update({member.display_name: base_file_name})
#                 logger.info("file name: %s", base_file_name)

#             voice.listen(MultiWaveSink(user_destinations=user_destinations))

#     @commands.command(name="stop")
#     async def stop(self, ctx):
#         await ctx.send("Disconnecting")
#         await ctx.voice_client.disconnect()

#         # results = [
#         #     f"{author}: {wav_to_text(file_name)}"
#         #     for author, file_name in self.file_names.items()
#         # ]
#         # results = [
#         #     wav_to_text(str(file_name)) for file_name in self.file_names.values()
#         # ]
#         # await asyncio.gather(*results)
#         # await ctx.send(results)

#     # @commands.Cog.listener()
#     # async def on_voice_state_update(
#     #     self,
#     #     member: discord.Member,
#     #     before: discord.VoiceState,
#     #     after: discord.VoiceState,
#     # ):
#     #     if before.channel is None and after.channel is not None:
#     #         return

#     #     file_name = self.file_names.pop(member.display_name, None)
#     #     if file_name is None:
#     #         return

#     #     result = await(wav_to_text(file_name))
#     #     await member.send(result)

# # def parse_all_wav_files(file_names):
