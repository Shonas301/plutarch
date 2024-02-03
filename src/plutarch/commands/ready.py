import logging

from dicord.ext import commands

logger = logging.getLogger(__name__)


class RecordAudio(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.connections = {}

    @commands.Cog.listener()
    async def on_ready(self, ctx):
        logger.info("Bot %s is ready", self.client.user)
