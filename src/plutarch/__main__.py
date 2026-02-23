import asyncio
import logging
import logging.handlers
import os

import discord
import nest_asyncio
from discord.ext import commands
from dotenv import load_dotenv

from .arc.cog import ArcStash
from .commands.audio_player import AudioLinkPlayer
from .commands.ready import ReadyConnection
from .commands.record_audio import RecordAudio
from .commands.voice_connections import ChannelStateManager

logger = logging.getLogger()

nest_asyncio.apply()


# setup logging
def init_logging() -> logging.Handler:
    logger.setLevel(os.getenv("LOGGING_LEVEL", logging.INFO))
    logging.getLogger("discord").setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        filename="discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )
    dt_fmt = "%H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return handler


# initialize client
def init_client():
    logger.info("Initializing discord bot")
    intents = discord.Intents.all()
    intents.message_content = True
    client = commands.Bot(intents=intents, command_prefix="%")
    return client


# initialize env, wrapping in a function incase future configs are needed
def init_env():
    load_dotenv()


async def init_cogs(client: commands.Bot):
    # create shared state manager for cogs that need it
    state_manager = ChannelStateManager()

    # initialize cogs with their dependencies
    logger.info("Initializing: ReadyConnection")
    await client.add_cog(ReadyConnection(client))

    logger.info("Initializing: AudioLinkPlayer")
    await client.add_cog(AudioLinkPlayer(client, state_manager))

    logger.info("Initializing: RecordAudio")
    await client.add_cog(RecordAudio(client, state_manager))

    logger.info("Initializing: ArcStash")
    await client.add_cog(ArcStash(client))


# entrypoint
async def main():
    init_env()
    log_handler = init_logging()
    client = init_client()
    async with client:
        await init_cogs(client)
        client.run(os.getenv("DISCORD_TOKEN"), log_handler=log_handler)


if __name__ == "__main__":
    asyncio.run(main())
