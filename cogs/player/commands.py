import disnake
from disnake.ext import commands
from datetime import datetime, timedelta
import asyncio
import pytz
from database.operations import save_player_link, get_player_by_discord_id, save_tracking_channel, update_trophy_count, \
    get_tracking_channels, get_tracking_channel, remove_tracking_channel
from services.coc_api import get_player_info


class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracking_tasks = {}
        self.bot.loop.create_task(self.schedule_daily_summary())
        # We'll set up tracking in on_ready instead of here

    async def setup_tracking_for_all_players(self):
        """Resume tracking for all players when bot starts"""
        try:
            # Wait until bot is fully ready
            await self.bot.wait_until_ready()

            # Get all tracking channels from database
            tracked_channels = await get_tracking_channels()
            print(f"Found {len(tracked_channels)} tracked players to resume")

            for channel_info in tracked_channels:
                try:
                    tag = channel_info["player_tag"]
                    channel_id = channel_info["channel_id"]

                    # Verify channel exists
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        print(f"Warning: Cannot find channel {channel_id} for player {tag}")
                        # Try to fetch the channel directly
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                            if channel:
                                print(f"Successfully fetched channel {channel_id}")
                        except Exception as e:
                            print(f"Error fetching channel {channel_id}: {e}")
                            continue

                    if channel:
                        # Start tracking task for each player
                        if tag not in self.tracking_tasks:
                            self.tracking_tasks[tag] = self.bot.loop.create_task(
                                self.track_trophies(tag, channel_id)
                            )
                            print(f"Resumed tracking for player {tag} in channel {channel.name} ({channel_id})")
                except Exception as e:
                    print(f"Error resuming tracking for player {tag}: {e}")
                    continue

        except Exception as e:
            print(f"Error setting up tracking for all players: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready. Set up tracking here."""
        print("Bot is ready, setting up tracking...")
        await self.setup_tracking_for_all_players()

    @commands.slash_command()
    async def player(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @player.sub_command()
    async def link(self, inter: disnake.ApplicationCommandInteraction, tag: str):
        """Link your Clash of Clans account with Discord

        Parameters
        ----------
        tag: Player tag to link with your Discord account
        """
        await inter.response.defer()

        # Remove # if present
        tag = tag.replace('#', '')

        try:
            player = await get_player_info(tag)
            await save_player_link(inter.author.id, tag)

            embed = disnake.Embed(
                title="Account Linked Successfully!",
                description=f"Your Discord account has been linked with CoC player: {player.name} ({player.tag})",
                color=disnake.Color.green()
            )
            await inter.edit_original_message(embed=embed)
        except Exception as e:
            await inter.edit_original_message(content=f"Error linking account: {str(e)}")

        # Add stop tracking command
        @player.sub_command()
        async def stop_tracking(self, inter: disnake.ApplicationCommandInteraction):
            """Stop tracking player"""
            await inter.response.defer()

            try:
                # Get player tag from database
                tag = await get_player_by_discord_id(inter.author.id)
                if not tag:
                    await inter.edit_original_message(content="You haven't linked any account!")
                    return

                # Cancel tracking task if exists
                if tag in self.tracking_tasks:
                    self.tracking_tasks[tag].cancel()
                    del self.tracking_tasks[tag]

                # Delete channel
                channel_info = await get_tracking_channel(tag)
                if channel_info:
                    channel = self.bot.get_channel(channel_info["channel_id"])
                    if channel:
                        await channel.delete()

                # Remove from database
                await remove_tracking_channel(tag)

                await inter.edit_original_message(content="✅ Stopped tracking player!")
            except Exception as e:
                await inter.edit_original_message(content=f"Error stopping tracker: {str(e)}")

    @player.sub_command()
    async def check(self, inter: disnake.ApplicationCommandInteraction, tag: str = None):
        """Check player information

        Parameters
        ----------
        tag: Player tag to check (optional if you've linked your account)
        """
        # Defer the response immediately
        await inter.response.defer()

        try:
            if not tag:
                stored_tag = await get_player_by_discord_id(inter.author.id)
                if not stored_tag:
                    await inter.edit_original_message(content="Please provide a player tag or link your account first!")
                    return
                tag = stored_tag
            else:
                tag = tag.replace('#', '')

            player = await get_player_info(tag)

            embed = disnake.Embed(
                title=f"Player Info: {player.name}",
                description=f"Tag: {player.tag}",
                color=disnake.Color.blue()
            )

            embed.add_field(name="Current Trophies", value=f"🏆 {player.trophies}", inline=True)
            embed.add_field(name="Best Trophies", value=f"🏆 {player.best_trophies}", inline=True)
            embed.add_field(name="League", value=player.league.name if player.league else "None", inline=True)

            if player.league and player.league.icon:
                embed.set_thumbnail(url=player.league.icon.url)

            embed.add_field(name="Town Hall", value=f"Level {player.town_hall}", inline=True)

            if player.clan:
                embed.add_field(name="Clan", value=f"{player.clan.name} ({player.clan.tag})", inline=True)
            else:
                embed.add_field(name="Clan", value="No Clan", inline=True)


            await inter.edit_original_message(embed=embed)
        except Exception as e:
            await inter.edit_original_message(content=f"Error checking player: {str(e)}")

    @player.sub_command()
    async def track(self, inter: disnake.ApplicationCommandInteraction, tag: str = None):
        """Track player trophy changes in Legend League

        Parameters
        ----------
        tag: Player tag to track (optional if you've linked your account)
        """
        await inter.response.defer()

        try:
            if not tag:
                stored_tag = await get_player_by_discord_id(inter.author.id)
                if not stored_tag:
                    await inter.edit_original_message(content="Please provide a player tag or link your account first!")
                    return
                tag = stored_tag
            else:
                tag = tag.replace('#', '')

            # Check if already tracking this player
            existing_channel = await get_tracking_channel(tag)
            if existing_channel:
                channel = self.bot.get_channel(existing_channel["channel_id"])
                if channel:
                    await inter.edit_original_message(
                        content=f"Already tracking this player in {channel.mention}!"
                    )
                    return

            player = await get_player_info(tag)

            # Check if player is in Legend League
            if not player.league or player.league.id != 29000022:  # 29000022 is Legend League ID
                await inter.edit_original_message(
                    content=f"❌ Cannot track {player.name} - Player must be in Legend League! Current league: {player.league.name if player.league else 'None'}"
                )
                return

            # Create tracking channel
            channel_name = f"{player.name}-trophy-tracker".lower().replace(' ', '-')
            tracking_channel = await inter.guild.create_text_channel(channel_name)

            # Save channel info to database
            await save_tracking_channel(inter.author.id, tag, tracking_channel.id)

            # Start tracking task
            if tag in self.tracking_tasks:
                self.tracking_tasks[tag].cancel()
            self.tracking_tasks[tag] = self.bot.loop.create_task(
                self.track_trophies(tag, tracking_channel.id)
            )

            await inter.edit_original_message(
                content=f"Now tracking {player.name}'s Legend League attacks in {tracking_channel.mention}!"
            )
        except Exception as e:
            await inter.edit_original_message(content=f"Error setting up tracking: {str(e)}")

    async def track_trophies(self, tag: str, channel_id: int):
        """Background task to track trophy changes"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"Could not find channel with ID {channel_id}")
            return

        last_trophies = None
        player = None
        status_message = None
        retries = 3  # Number of retries for API calls

        # Get initial trophy count with retries
        for attempt in range(retries):
            try:
                player = await get_player_info(tag)
                if player and player.league:
                    # Check if player is still in Legend League
                    if player.league.id != 29000022:
                        await channel.send(f"❌ Stopping tracker - {player.name} is no longer in Legend League!")
                        return

                    last_trophies = player.trophies
                    print(f"Starting Legend League trophy tracking for {player.name} at {last_trophies} trophies")
                    await channel.send(
                        f"🏆 Starting Legend League trophy tracking for {player.name} at {last_trophies} trophies")
                    status_message = await channel.send(f"Monitoring {player.name}'s trophy count...")
                    break
            except Exception as e:
                print(f"Error on attempt {attempt + 1}/{retries} getting initial trophy count: {e}")
                if attempt == retries - 1:  # Last attempt failed
                    print(f"Failed to initialize tracking for {tag} after {retries} attempts")
                    await channel.send(
                        f"❌ Failed to initialize tracking after {retries} attempts. Please try again later.")
                    return
                await asyncio.sleep(2)  # Wait before retry

        while True:
            try:
                await asyncio.sleep(60)  # Wait for 1 minute before checking again

                player = await get_player_info(tag)
                if not player or not player.league:
                    print(f"Error: Could not get player info for {tag}")
                    continue

                # Check if player is still in Legend League
                if player.league.id != 29000022:
                    await channel.send(f"❌ Stopping tracker - {player.name} is no longer in Legend League!")
                    return

                current_trophies = player.trophies

                # If trophy count changed, send a message
                if current_trophies != last_trophies:
                    # Clear status message on trophy change
                    if status_message:
                        await status_message.delete()

                    trophy_change = current_trophies - last_trophies
                    message = self.format_legend_league_change(player.name, trophy_change)

                    # Only send message if it's not None (skip 3-star defenses)
                    if message:
                        print(f"Trophy change detected for {player.name}: {trophy_change}")
                        await channel.send(message)

                    last_trophies = current_trophies
                    # Create new status message
                    status_message = await channel.send(f"Monitoring {player.name}'s trophy count...")

            except asyncio.CancelledError:
                print(f"Stopping trophy tracking for {player.name if player else tag} - Bot shutdown")
                if status_message:
                    await status_message.delete()
                await channel.send(f"🛑 Trophy tracking stopped - Bot shutdown")
                return

            except Exception as e:
                print(f"Error in trophy tracking loop for {tag}: {e}")
                await asyncio.sleep(5)  # Wait a bit longer on error

    def format_legend_league_change(self, player_name: str, trophy_change: int) -> str:
        """Format trophy change message specifically for Legend League"""
        if trophy_change > 0:
            if trophy_change == 40:  # Exactly 40 for 3-star
                return (f" **ATTACK WON!** \n"
                        f"{player_name} got a 3-star attack!\n"
                        f"Trophy change: +{trophy_change} 🏆")
            elif 16 <= trophy_change <= 32:  # Range 16-32 for 2-star
                return (f" **ATTACK WON!** \n"
                        f"{player_name} got a 2-star attack!\n"
                        f"Trophy change: +{trophy_change} 🏆")
            elif 1 <= trophy_change <= 15:  # Range 1-15 for 1-star
                return (f" **ATTACK WON!** \n"
                        f"{player_name} got a 1-star attack!\n"
                        f"Trophy change: +{trophy_change} 🏆")
            else:
                return (f"⚔️ **LEGEND LEAGUE ATTACK!** ⚔️\n"
                        f"{player_name} gained some trophies\n"
                        f"Trophy change: +{trophy_change} 🏆")
        else:
            trophy_change = abs(trophy_change)
            # Skip notification for 3-star defenses (40 trophy loss)
            if trophy_change == 40:
                return None  # Return None to indicate no message should be sent
            elif 16 <= trophy_change <= 32:  # Range 16-32 for 2-star defense
                return (f" **DEFENSE LOST!** \n"
                        f"{player_name}'s base was 2-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")
            elif 1 <= trophy_change <= 15:  # Range 1-15 for 1-star defense
                return (f" **DEFENSE LOST!** \n"
                        f"{player_name}'s base was 1-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")
            else:
                return (f"🛡️ **LEGEND LEAGUE DEFENSE!** 🛡️\n"
                        f"{player_name} lost some trophies\n"
                        f"Trophy change: -{trophy_change} 🏆")

    def format_trophy_change(self, player_name: str, trophy_change: int) -> str:
        """Format trophy change message"""
        if trophy_change > 0:
            if trophy_change == 40:
                return (f"**3-STAR ATTACK!**\n"
                        f"{player_name} won a perfect attack!\n"
                        f"Trophy change: +{trophy_change} 🏆")
            elif trophy_change >= 16:
                return (f"**2-STAR ATTACK!**\n"
                        f"{player_name} had a successful attack!\n"
                        f"Trophy change: +{trophy_change} 🏆")
            else:
                return (f"**1-STAR ATTACK!**\n"
                        f"{player_name} got some damage in!\n"
                        f"Trophy change: +{trophy_change} 🏆")
        else:
            trophy_change = abs(trophy_change)
            if trophy_change == 40:
                return (f"**DEFENSE LOST!**\n"
                        f"{player_name}'s base was 3-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")
            elif trophy_change >= 16:
                return (f"**DEFENSE LOST!**\n"
                        f"{player_name}'s base was 2-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")
            else:
                return (f"**DEFENSE LOST!**\n"
                        f"{player_name}'s base was 1-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")

    async def schedule_daily_summary(self):
        """Schedule daily trophy summary at 10 PM GMT-7"""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            # Get current time in GMT-7
            tz = pytz.timezone('America/Los_Angeles')
            now = datetime.now(tz)

            # Calculate time until next 10 PM
            if now.hour >= 22:
                next_summary = now + timedelta(days=1)
            else:
                next_summary = now
            next_summary = next_summary.replace(hour=22, minute=0, second=0, microsecond=0)

            # Sleep until next summary time
            await asyncio.sleep((next_summary - now).total_seconds())

            # Run summary for all tracked players
            await self.run_daily_summary()

    @player.sub_command()
    async def force_summary(self, inter: disnake.ApplicationCommandInteraction):
        """Force a daily trophy summary (Testing command)"""
        await inter.response.defer()

        try:
            await self.run_daily_summary()
            await inter.edit_original_message(content="✅ Daily summary has been forced!")
        except Exception as e:
            await inter.edit_original_message(content=f"❌ Error running summary: {str(e)}")

    async def run_daily_summary(self):
        """Run daily trophy summary for all tracked players"""
        # Get all tracking channels from database
        tracked_channels = await get_tracking_channels()

        for channel_info in tracked_channels:
            try:
                channel = self.bot.get_channel(channel_info["channel_id"])
                if not channel:
                    print(f"Could not find channel {channel_info['channel_id']}")
                    continue

                tag = channel_info["player_tag"]
                player = await get_player_info(tag)

                # Check if player is still in Legend League
                if not player.league or player.league.id != 29000022:
                    await channel.send(f"❌ Daily Summary: {player.name} is no longer in Legend League!")
                    continue

                # Get the starting trophy count (if available)
                start_trophies = channel_info.get("daily_start_trophy")
                if start_trophies is None:
                    start_trophies = player.trophies

                # Calculate trophy change
                trophy_change = player.trophies - start_trophies

                # Create summary embed
                embed = disnake.Embed(
                    title="📊 Daily Trophy Summary",
                    description=f"Summary for {player.name}",
                    color=disnake.Color.blue()
                )

                embed.add_field(
                    name="Trophy Change",
                    value=f"{'🔺' if trophy_change >= 0 else '🔻'} {trophy_change:+d}",
                    inline=False
                )

                embed.add_field(
                    name="Starting Trophies",
                    value=f"🏆 {start_trophies}",
                    inline=True
                )

                embed.add_field(
                    name="Current Trophies",
                    value=f"🏆 {player.trophies}",
                    inline=True
                )

                if player.clan:
                    embed.add_field(
                        name="Clan",
                        value=f"{player.clan.name}",
                        inline=True
                    )

                # Add rankings
                global_rank = f"🌐 {player.global_rank:,} (Top {player.global_rank_percentage:.2f}%)" if player.global_rank else "🌐 Unranked"
                local_rank = f"🏳️ {player.local_rank} ({player.country_name})" if player.local_rank else f"🏳️ Unranked ({player.country_name})"

                embed.add_field(
                    name="Rankings",
                    value=f"{global_rank}\n{local_rank}",
                    inline=False
                )

                # Set thumbnail if league icon is available
                if player.league and player.league.icon:
                    embed.set_thumbnail(url=player.league.icon.url)

                # Add timestamp
                embed.timestamp = datetime.now()

                await channel.send(embed=embed)

                # Update the daily start trophy count for tomorrow
                await update_trophy_count(tag, player.trophies, is_daily=True)

            except Exception as e:
                print(f"Error generating summary for channel {channel_info['channel_id']}: {e}")

def setup(bot):
    bot.add_cog(PlayerCommands(bot))