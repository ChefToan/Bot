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
        # Clear all existing commands first
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        logger.info("Cleared existing commands")

        # Initialize COC client
        try:
            self.coc_client = await setup_coc_client()
            logger.info("COC client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            await self.close()
            return

        # Add cogs
        try:
            await self.add_cog(PlayerCommands(self, self.coc_client))
            logger.info("PlayerCommands cog loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load PlayerCommands cog: {e}")
            return

        # Sync commands
        try:
            logger.info("Starting command sync...")
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} command(s)")
            for cmd in synced:
                logger.info(f"Synced command: {cmd.name}")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Registered commands:")
        for cmd in self.tree.get_commands():
            logger.info(f"- {cmd.name}")

def main():
    bot = CocTrackerBot()
    try:
        bot.run(Config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise

if __name__ == "__main__":
    main()