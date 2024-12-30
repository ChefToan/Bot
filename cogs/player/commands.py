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

        # Get current time in GMT-7
        tz = pytz.timezone('America/Los_Angeles')
        current_time = datetime.now(tz)

        # Get initial trophy count with retries
        for attempt in range(3):
            try:
                player = await get_player_info(tag)
                if player and player.league:
                    # Check if player is still in Legend League
                    if player.league.id != 29000022:
                        await channel.send(f"❌ Stopping tracker - {player.name} is no longer in Legend League!")
                        return

                    last_trophies = player.trophies

                    # Check if it's past 9 PM GMT-7 and we need to set initial trophies
                    if current_time.hour >= 21:  # 9 PM or later
                        await update_trophy_count(tag, last_trophies, is_daily=True)
                        print(f"Setting initial trophy count for {player.name} at {last_trophies} (9 PM GMT-7)")
                    else:
                        channel_info = await get_tracking_channel(tag)
                        if channel_info and channel_info.get("daily_start_trophy") is None:
                            # If no daily start trophy is set, set it to 0 until 9 PM
                            await update_trophy_count(tag, 0, is_daily=True)
                            print(f"Setting temporary trophy count of 0 for {player.name} until 9 PM GMT-7")

                    print(f"Starting Legend League trophy tracking for {player.name} at {last_trophies} trophies")
                    await channel.send(
                        f"🏆 Starting Legend League trophy tracking for {player.name} at {last_trophies} trophies")
                    break
            except Exception as e:
                print(f"Error on attempt {attempt + 1}/3 getting initial trophy count for {tag}: {e}")
                await asyncio.sleep(2)

        if last_trophies is None:
            await channel.send(f"❌ Failed to initialize tracking. Please try again later.")
            return

        check_interval = 30  # Check every 30 seconds

        while True:
            try:
                await asyncio.sleep(check_interval)

                # Get current time in GMT-7
                current_time = datetime.now(tz)

                # Get latest player info
                player = await get_player_info(tag)
                if not player or not player.league:
                    print(f"Warning: Could not get player info for {tag}")
                    continue

                # Check if it's 9 PM GMT-7 and we need to record daily start trophies
                if current_time.hour == 21 and current_time.minute == 0:
                    await update_trophy_count(tag, player.trophies, is_daily=True)
                    print(f"Updated daily start trophies for {player.name} to {player.trophies}")

                # Rest of your existing trophy tracking code...
                # (Keep the rest of the while loop code as is)

            except asyncio.CancelledError:
                print(f"Stopping trophy tracking for {player.name if player else tag}")
                await channel.send(f"🛡️ Trophy tracking stopped for {player.name if player else tag}")
                return

            except Exception as e:
                print(f"Error in trophy tracking loop for {tag}: {e}")
                await asyncio.sleep(5)
                continue

    def format_legend_league_change(self, player_name: str, trophy_change: int) -> str:
        """Format trophy change message specifically for Legend League"""
        if trophy_change > 0:
            if trophy_change == 40:  # Exactly 40 for 3-star
                return (f"⚔️ **ATTACK WON!** \n"
                        f"{player_name} got a 3-star attack!\n"
                        f"Trophy change: +{trophy_change} 🏆")
            elif 16 <= trophy_change <= 32:  # Range 16-32 for 2-star
                return (f"⚔️ **ATTACK WON!** \n"
                        f"{player_name} got a 2-star attack!\n"
                        f"Trophy change: +{trophy_change} 🏆")
            elif 1 <= trophy_change <= 15:  # Range 1-15 for 1-star
                return (f"⚔️ **ATTACK WON!** \n"
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
                return (f"🛡️ **DEFENSE LOST!** \n"
                        f"{player_name}'s base was 3-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")
            elif 16 <= trophy_change <= 32:  # Range 16-32 for 2-star defense
                return (f"🛡️ **DEFENSE LOST!** \n"
                        f"{player_name}'s base was 2-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")
            elif 1 <= trophy_change <= 15:  # Range 1-15 for 1-star defense
                return (f"🛡️ **DEFENSE LOST!** \n"
                        f"{player_name}'s base was 1-starred\n"
                        f"Trophy change: -{trophy_change} 🏆")
            else:
                return (f"🛡️ **DEFENSE RESULT** 🛡️\n"
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
        """Schedule daily trophy summary at 9 PM GMT-7"""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            # Get current time in GMT-7
            tz = pytz.timezone('America/Los_Angeles')
            now = datetime.now(tz)

            # Calculate time until next 9 PM
            if now.hour >= 21:  # If it's past 9 PM
                next_summary = now + timedelta(days=1)  # Schedule for tomorrow
            else:
                next_summary = now
            next_summary = next_summary.replace(hour=21, minute=0, second=0, microsecond=0)

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