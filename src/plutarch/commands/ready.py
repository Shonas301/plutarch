import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class ReadyConnection(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.connections = {}

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Bot %s is ready", self.client.user)
        # Set bot status
        await self.client.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="time"),
            status="online",
        )
