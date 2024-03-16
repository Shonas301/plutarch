import asyncio
import logging
import os
import wave
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

import discord
import pytz
from discord.ext import commands, voice_recv
from discord.opus import Decoder as OpusDecoder

from plutarch.commands.state_interface import VoiceChannelCog, VoiceMeta
from plutarch.transcribe.transcribe_wav import wav_to_text

logger = logging.getLogger(__name__)
discord.opus._load_default()


@dataclass
class ChannelState:
    channel: discord.VoiceChannel
    client: discord.VoiceClient | None = None
    file_names: Mapping[str, str] = field(default_factory=list)


class MultiWaveSink(voice_recv.AudioSink):
    """Endpoint AudioSink that generates a wav file for multiple users.

    Best used in conjunction with a silence generating sink. (TBD)

    Attributes:
        CHANNELS (int): System audio channels
        SAMPLE_WIDTH (int) = Ration of system audio sample size to channels
        SAMPLING_RATE (int)= System audio sampling rang
    """

    CHANNELS = OpusDecoder.CHANNELS
    SAMPLE_WIDTH = OpusDecoder.SAMPLE_SIZE // OpusDecoder.CHANNELS
    SAMPLING_RATE = OpusDecoder.SAMPLING_RATE

    def __init__(self, user_destinations: dict[str, str]):
        super().__init__()

        self._files: dict[str, wave.Wave_write] = {}
        for user_name, file_loc in user_destinations.items():
            self._files[user_name] = self.init_file(file_loc)

    def init_file(self, file_name: str) -> wave.Wave_write:
        file = wave.open(file_name, "wb")
        file.setnchannels(self.CHANNELS)
        file.setsampwidth(self.SAMPLE_WIDTH)
        file.setframerate(self.SAMPLING_RATE)
        return file

    def wants_opus(self) -> bool:
        return False

    def write(
        self, user: discord.User | discord.Member | None, data: voice_recv.VoiceData
    ) -> None:
        if user is None:
            return
        if self._files.get(user.display_name):
            self._files[user.display_name].writeframes(data.pcm)

    def cleanup(self) -> None:
        try:
            for file in self._files.values():
                file.close()
        except Exception:
            logger.exception()


class RecordAudio(commands.Cog, VoiceChannelCog, metaclass=VoiceMeta):
    def __init__(self, client):
        logger.info("Initializing recording commands")
        self.client = client
        self.file_names = {}
        self.channels_info: Mapping[int, ChannelState] = {}

    @commands.command(name="record")
    async def record(self, ctx: commands.Context):
        channel = ctx.author.voice.channel
        channel_info = ChannelState
        self.channels_info[channel.id] = channel_info

        if channel is None:
            await ctx.send("You're not in a voice chat", ephemeral=True)
            return

        await ctx.send("starting VC recording session")

        channel_info.client = await channel.connect(cls=voice_recv.VoiceRecvClient)
        channel_info.file_names = self.generate_file_names(channel)
        channel_info.client.listen(
            MultiWaveSink(user_destinations=channel_info.file_names)
        )

    @commands.command(name="stop-recording")
    async def stop_recording(self, ctx):
        await ctx.send("Disconnecting")
        await ctx.voice_client.disconnect()

        transcriptions = [
            wav_to_text(str(file_name))
            for file_name in self.channels_info[
                ctx.author.voice.channel.id
            ].file_names.values()
        ]
        results = await asyncio.gather(*transcriptions)
        await ctx.send(results)

    def generate_file_names(
        self, channel: discord.VoiceChannel | discord.StageChannel
    ) -> dict[str, str]:
        time = datetime.now(pytz.utc)
        user_file_paths = {}

        def format_file(name):
            return name + f"{time.day}_{time.hour}_{time.second}" + ".wav"

        for member in channel.members:
            if member.display_name == os.getenv("DISCORD_BOT_NAME"):
                continue
            if member.display_name == "plutarch":
                continue

            base_file_name = format_file(member.display_name)
            user_file_paths[member.display_name] = base_file_name
            logger.info("file name: %s", base_file_name)
        user_file_paths[channel.name] = format_file(channel.name)
        return user_file_paths

    async def leave_voice_channel(
        self, channel: discord.VoiceChannel | discord.StageChannel
    ) -> None:
        client = self.channels_info[channel.id].client
        if client is None:
            return
        client.stop()
