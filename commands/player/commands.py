import discord
from discord import app_commands
from discord.ext import commands
import coc


class PlayerCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, coc_client: coc.Client):
        self.bot = bot
        self.coc = coc_client

    @app_commands.command(name="player")
    @app_commands.describe(
        tag="Player tag (without #)",
        action="Choose to check or track trophies"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="check", value="check"),
        app_commands.Choice(name="track", value="track")
    ])
    async def player_command(self, interaction: discord.Interaction, action: str, tag: str):
        await interaction.response.defer()

        if not tag.startswith('#'):
            tag = f'#{tag}'

        try:
            player = await self.coc.get_player(tag)

            if action == "check":
                embed = discord.Embed(
                    title=f"{player.name} ({player.tag})",
                    description="Player Information",
                    color=discord.Color.green()
                )

                # Trophy Information
                embed.add_field(name="Current Trophy", value=f"🏆 {player.trophies}", inline=True)
                embed.add_field(name="Best Trophies", value=f"🏆 {player.best_trophies}", inline=True)
                embed.add_field(name="League", value=player.league.name if player.league else "Unranked", inline=True)

                # Player Information
                embed.add_field(name="Town Hall", value=f"🏰 Level {player.town_hall}", inline=True)

                if player.clan:
                    clan_info = f"{player.clan.name} ({player.clan.tag})"
                    embed.add_field(name="Clan", value=clan_info, inline=True)

                if player.league and player.league.icon:
                    embed.set_thumbnail(url=player.league.icon.url)

                await interaction.followup.send(embed=embed)

            elif action == "track":
                await interaction.followup.send(f"Trophy tracking for {player.name} will be implemented soon!")

        except coc.NotFound:
            await interaction.followup.send("Player not found!")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    async def cog_unload(self) -> None:
        self.bot.tree.clear_commands(guild=None)