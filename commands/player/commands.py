import discord
from discord import app_commands
from discord.ext import commands
from services.coc_service import CocService


class PlayerCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, coc_service: CocService):
        self.bot = bot
        self.coc_service = coc_service

    @app_commands.command(name="player")
    @app_commands.describe(tag="Player tag (without #)")
    async def player_info(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer()

        # Add # if not present
        if not tag.startswith('#'):
            tag = f'#{tag}'

        player_data = await self.coc_service.get_player_info(tag)

        if not player_data:
            await interaction.followup.send("Player not found or invalid tag!")
            return

        embed = discord.Embed(title=f"Player Info: {player_data['name']}")
        embed.add_field(name="Trophy Count", value=f"🏆 {player_data['trophy_count']}", inline=True)
        embed.add_field(name="Best Trophies", value=f"🏆 {player_data['best_trophies']}", inline=True)
        embed.add_field(name="League", value=player_data['league'], inline=True)

        embed.add_field(name="Town Hall", value=f"🏰 Level {player_data['town_hall_level']}", inline=True)

        if player_data['clan_name']:
            clan_info = f"{player_data['clan_name']} ({player_data['clan_tag']})"
            embed.add_field(name="Clan", value=clan_info, inline=True)

        await interaction.followup.send(embed=embed)