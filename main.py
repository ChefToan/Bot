import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from services.coc_service import CocService
from commands.player.commands import PlayerCommands
import asyncio

load_dotenv()


class CocTrackerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Enable message content intent
        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        self.coc_service = CocService()
        await self.coc_service.initialize()  # Initialize COC client

        await self.add_cog(PlayerCommands(self, self.coc_service))

        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def close(self):
        await self.coc_service.close()  # Close COC client
        await super().close()


def main():
    bot = CocTrackerBot()
    bot.run(os.getenv('DISCORD_TOKEN'))


if __name__ == "__main__":
    main()