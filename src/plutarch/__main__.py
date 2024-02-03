import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Initialize client
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(intents=intents, command_prefix='%')

# Initialize env
load_dotenv()

if __name__ == "__main__":
    print("Starting Plutarch")
    client.run(os.getenv('DISCORD_TOKEN'))
