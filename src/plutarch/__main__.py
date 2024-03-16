import asyncio
import logging
import logging.handlers
import os

import discord
import nest_asyncio
from discord.ext import commands
from dotenv import load_dotenv

from .commands import cogs

logger = logging.getLogger("discord")

nest_asyncio.apply()


# setup logging
def init_logging():
    logger.setLevel(logging.DEBUG)
    logging.getLogger("discord.http").setLevel(logging.DEBUG)

    handler = logging.handlers.RotatingFileHandler(
        filename="discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )
    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# initialize client
def init_client():
    logger.info("Initializing discord bot")
    intents = discord.Intents.all()
    intents.message_content = True
    client = commands.Bot(intents=intents, command_prefix="%")
    return client


# initialize env, wrapping in a function incase future configs are needed
def init_env():
    logger.info("Initializing environment")
    load_dotenv()


async def init_cogs(client: commands.Bot):
    for cog in cogs:
        logger.info("Initializing: %s", cog.__name__)
        await client.add_cog(cog(client))


# entrypoint
async def main():
    init_logging()
    init_env()
    client = init_client()
    async with client:
        await init_cogs(client)
        client.run(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
