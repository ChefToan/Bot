import discord
from discord.ext import commands
from utils.config import Config, setup_logging, setup_coc_client
from commands.player.commands import PlayerCommands

logger = setup_logging()


class CocTrackerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        # Initialize COC client
        try:
            self.coc_client = await setup_coc_client()
            logger.info("COC client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            await self.close()
            return

        # Add cogs
        await self.add_cog(PlayerCommands(self, self.coc_client))
        logger.info("Cogs loaded successfully")

        # Sync commands
        await self.tree.sync()
        logger.info("Command tree synced")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def close(self):
        if hasattr(self, 'coc_client'):
            await self.coc_client.close()
        await super().close()


def main():
    bot = CocTrackerBot()
    try:
        bot.run(Config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise


if __name__ == "__main__":
    main()