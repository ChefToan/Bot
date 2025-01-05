import asyncio
import discord
from discord.ext import commands
import sys
import signal

from services.coc_api import close_coc_client
from utils.config import DISCORD_TOKEN
from database.mongo_utils import close_database


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

    async def setup_hook(self):
        """Called when the bot is setting up"""
        # Load cogs here instead of in main()
        await self.load_extension("cogs.player.commands")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def close(self):
        """Cleanup when bot shuts down"""
        print("Bot is shutting down...")

        # Cancel all tracking tasks
        for cog in self.cogs.values():
            if hasattr(cog, 'tracking_tasks'):
                for task in cog.tracking_tasks.values():
                    task.cancel()

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
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())