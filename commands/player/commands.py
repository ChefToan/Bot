import discord
from discord import app_commands
from discord.ext import commands
import coc

class CustomTownHall:
    def __init__(self, level):
        self._level = level

    def __str__(self):
        return str(self._level)

    def __int__(self):
        return self._level

    @property
    def image_url(self):
        return f'https://assets.clashk.ing/home-base/town-hall-pics/town-hall-{self._level}.png'

class PlayerCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, coc_client: coc.Client):
        self.bot = bot
        self.coc = coc_client

    @app_commands.command(name="player")
    @app_commands.describe(tag="Player tag (without #)")
    async def player_info(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer()

        # Add # if not present
        if not tag.startswith('#'):
            tag = f'#{tag}'

        try:
            player = await self.coc.get_player(tag)
            town_hall = CustomTownHall(player.town_hall)

            embed = discord.Embed(
                title=f"{player.name} ({player.tag})",
                description="Player Information",
                color=discord.Color.green()
            ).set_thumbnail(url=town_hall.image_url)

            embed.add_field(name="Current Trophy", value=f"🏆 {player.trophies}", inline=True)
            embed.add_field(name="Best Trophies", value=f"🏆 {player.best_trophies}", inline=True)
            embed.add_field(name="League", value=player.league.name if player.league else "Unranked", inline=True)
            embed.add_field(name="Town Hall", value=f"🏰 Level {player.town_hall}", inline=True)

            if player.clan:
                clan_info = f"{player.clan.name} ({player.clan.tag})"
                embed.add_field(name="Clan", value=clan_info, inline=True)

            # Set league icon as thumbnail
            if player.league and player.league.icon:
                embed.set_thumbnail(url=player.league.icon.url)

            await interaction.followup.send(embed=embed)

        except coc.NotFound:
            await interaction.followup.send("Player not found!")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")