import asyncio
import os

import discord
from discord.ext import commands
import sys
import signal
import wavelink
import logging
from typing import Optional
from dotenv import load_dotenv

from services.coc_api import close_coc_client
from services.potoken_generator import start_token_manager
from utils.config import DISCORD_TOKEN
from database.mongo_utils import close_database

# Load environment variables
load_dotenv()

LAVALINK_URI = os.getenv('LAVALINK_URI')
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD')

# Set up logging
logging.basicConfig(level=logging.INFO)


class ClashBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True

        super().__init__(
            command_prefix="!",
            intents=intents
        )

        # Store token manager
        self.token_manager = None

    async def setup_hook(self):
        """Called when the bot is setting up"""
        # Start Lavalink setup
        try:
            # Start token manager
            self.token_manager = await start_token_manager()

            # Get initial tokens
            await self.token_manager.get_token()

            # Wavelink 3.0+ node setup
            node = wavelink.Node(
                uri=LAVALINK_URI,
                password=LAVALINK_PASSWORD
            )
            await wavelink.Pool.connect(client=self, nodes=[node])
            logging.info("Wavelink node connected successfully!")
        except Exception as e:
            logging.error(f"Failed to setup music services: {e}")

        # Load cogs
        await self.load_extension("cogs.player.commands")
        await self.load_extension("cogs.music.commands")  # Load music commands

        # Sync slash commands
        await self.tree.sync()
        logging.info("Slash commands synced!")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

        # Additional sync to ensure commands are registered
        for guild in self.guilds:
            try:
                await self.tree.sync(guild=guild)
                logging.info(f"Synced commands for guild: {guild.name}")
            except Exception as e:
                logging.error(f"Failed to sync commands for guild {guild.name}: {e}")

    async def close(self):
        """Cleanup when bot shuts down"""
        print("Bot is shutting down...")

        # Cancel all tracking tasks
        for cog in self.cogs.values():
            if hasattr(cog, 'tracking_tasks'):
                for task in cog.tracking_tasks.values():
                    task.cancel()

        try:
            # Disconnect from all voice channels
            for guild in self.guilds:
                if guild.voice_client:
                    await guild.voice_client.disconnect()
        except Exception as e:
            logging.error(f"Error disconnecting from voice channels: {e}")

        # Close COC client
        await close_coc_client()

        # Close database connection
        await close_database()

        # Close bot connection
        await super().close()
        print("Cleanup complete")


def handle_exit(signum, frame):
    print("\nReceived exit signal. Initiating shutdown...")
    sys.exit(0)


async def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_exit)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, handle_exit)  # Handle termination signal

    bot = ClashBot()

    try:
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Received keyboard interrupt, shutting down...")
        await bot.close()
    except Exception as e:
        print(f"Error occurred: {e}")
        await bot.close()
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())