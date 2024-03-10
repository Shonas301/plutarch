import asyncio
import logging
from abc import ABCMeta, abstractclassmethod
from functools import cache

from discord import Member, VoiceChannel, VoiceState
from discord.ext import commands

logger = logging.getLogger(__name__)
COGS = []


class VoiceChannelCog(metaclass=ABCMeta):
    @abstractclassmethod
    async def leave_voice_channel(self, channel: VoiceChannel):
        pass

    def join_active_cogs(self):
        cogs = active_cogs()
        cogs.append(self)


VoiceChannelCog.register(commands.Cog)


class VoiceStateManager(commands.Cog):
    def __init__(self, client):
        logger.info("Initializing recording commands")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ):
        active_voice_cogs = active_cogs()
        if after.channel is None:
            await asyncio.gather(
                *[
                    VoiceStateManager.leave_if_channel_empty(cog, before.channel)
                    for cog in active_voice_cogs
                ]
            )

    @staticmethod
    async def leave_if_channel_empty(cog: commands.Cog, previous_channel: VoiceChannel):
        member_count = len(previous_channel.members)
        if member_count == 0:
            cog.leave_voice_channel(previous_channel)


@cache
def active_cogs():
    return COGS
