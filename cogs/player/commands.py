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
        self.timezone = pytz.timezone('America/Phoenix')
        self.bot.loop.create_task(self.schedule_daily_summary())

    async def setup_tracking_for_all_players(self):
        """Resume tracking for all players when bot starts"""
        try:
            await self.bot.wait_until_ready()
            tracked_channels = await get_tracking_channels()
            print(f"Found {len(tracked_channels)} tracked players to resume")

            for channel_info in tracked_channels:
                try:
                    tag = channel_info["player_tag"]
                    channel_id = channel_info["channel_id"]

                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        print(f"Warning: Cannot find channel {channel_id} for player {tag}")
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                            if channel:
                                print(f"Successfully fetched channel {channel_id}")
                        except Exception as e:
                            print(f"Error fetching channel {channel_id}: {e}")
                            continue

                    if channel:
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


    @player.sub_command()
    async def stop_tracking(self, inter: disnake.ApplicationCommandInteraction):
        """Stop tracking player"""
        await inter.response.defer()

        try:
            tag = await get_player_by_discord_id(inter.author.id)
            if not tag:
                await inter.edit_original_message(content="You haven't linked any account!")
                return

            if tag in self.tracking_tasks:
                self.tracking_tasks[tag].cancel()
                del self.tracking_tasks[tag]

            channel_info = await get_tracking_channel(tag)
            if channel_info:
                channel = self.bot.get_channel(channel_info["channel_id"])
                if channel:
                    await channel.delete()

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
        last_update_time = None

        # Initialize tracking with retries
        for attempt in range(3):
            try:
                player = await get_player_info(tag)
                if player and player.league:
                    if player.league.id != 29000022:
                        await channel.send(f"❌ Stopping tracker - {player.name} is no longer in Legend League!")
                        return

                    last_trophies = player.trophies
                    channel_info = await get_tracking_channel(tag)

                    # Set initial trophy count to 0 if no daily_start_trophy is set
                    if channel_info and channel_info.get("daily_start_trophy") is None:
                        await update_trophy_count(tag, 0, is_daily=True)
                        print(f"Setting initial trophy count for {player.name} to 0 until next 10 PM reset")

                    await channel.send(
                        f"🏆 Starting Legend League trophy tracking for {player.name} at {last_trophies} trophies")

                    # # Add note about waiting for next reset
                    # current_time = datetime.now(self.timezone)
                    # if current_time.hour >= 22:
                    #     await channel.send("Note: Trophy tracking will begin with tomorrow's 10 PM reset")
                    # else:
                    #     await channel.send("Note: Trophy tracking will begin with today's 10 PM reset")


                    break
            except Exception as e:
                print(f"Error on attempt {attempt + 1}/3 getting initial trophy count for {tag}: {e}")
                await asyncio.sleep(2)

        if last_trophies is None:
            await channel.send(f"❌ Failed to initialize tracking. Please try again later.")
            return

        while True:
            try:
                await asyncio.sleep(30)
                current_time = datetime.now(self.timezone)

                player = await get_player_info(tag)
                if not player or not player.league:
                    continue

                if player.league.id != 29000022:
                    await channel.send(f"❌ Stopping tracker - {player.name} is no longer in Legend League!")
                    return

                # Check for 10 PM update only once
                if current_time.hour == 22 and current_time.minute == 0:
                    if last_update_time is None or (
                            current_time.date() > last_update_time.date() or
                            (current_time.date() == last_update_time.date() and
                             current_time.hour > last_update_time.hour)
                    ):
                        await update_trophy_count(tag, player.trophies, is_daily=True)
                        print(
                            f"Updated daily start trophies for {player.name} to {player.trophies} at 10 PM Phoenix time")
                        last_update_time = current_time
                # if current_time.hour == 17 and current_time.minute == 50:
                #     if last_update_time is None or (
                #             current_time.date() > last_update_time.date() or
                #             (current_time.date() == last_update_time.date() and
                #              current_time.hour > last_update_time.hour)
                #     ):
                #         await update_trophy_count(tag, player.trophies, is_daily=True)
                #         print(
                #             f"Updated daily start trophies for {player.name} to {player.trophies} at 5:30 PM Phoenix time")
                #         last_update_time = current_time

                # Trophy change tracking
                current_trophies = player.trophies
                if current_trophies != last_trophies:
                    trophy_change = current_trophies - last_trophies
                    message = self.format_legend_league_change(player.name, trophy_change)
                    await channel.send(message)
                    last_trophies = current_trophies
                    await update_trophy_count(tag, current_trophies, is_daily=False)

            except asyncio.CancelledError:
                print(f"Stopping trophy tracking for {player.name if player else tag}")
                await channel.send(f"🔴 Trophy tracking stopped for {player.name if player else tag}")
                return
            except Exception as e:
                print(f"Error in trophy tracking loop for {tag}: {e}")
                await asyncio.sleep(5)


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
            if trophy_change == 40:  # Exactly 40 for 3-star defense
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
        """Schedule daily trophy summary at 10 PM Phoenix time"""
        await self.bot.wait_until_ready()
        last_summary_date = None

        while not self.bot.is_closed():
            try:
                now = datetime.now(self.timezone)

                if now.hour >= 22:
                    next_summary = now + timedelta(days=1)
                else:
                    next_summary = now
                next_summary = next_summary.replace(hour=22, minute=0, second=0, microsecond=0)
                # if now.hour >= 17 and now.minute >= 50:
                #     next_summary = now + timedelta(days=1)
                # else:
                #     next_summary = now
                # next_summary = next_summary.replace(hour=17, minute=50, second=0, microsecond=0)

                sleep_seconds = (next_summary - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

                current_date = datetime.now(self.timezone).date()
                if last_summary_date != current_date:
                    await self.run_daily_summary()
                    last_summary_date = current_date
                    print(f"Daily summary completed at {datetime.now(self.timezone)}")

            except Exception as e:
                print(f"Error in schedule_daily_summary: {e}")
                await asyncio.sleep(60)


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
        tracked_channels = await get_tracking_channels()
        current_time = datetime.now(self.timezone)

        print(f"Sending daily summary to {len(tracked_channels)} players")

        for channel_info in tracked_channels:
            try:
                channel = self.bot.get_channel(channel_info["channel_id"])
                if not channel:
                    print(f"Could not find channel {channel_info['channel_id']}")
                    continue

                tag = channel_info["player_tag"]
                player = await get_player_info(tag)

                if not player.league or player.league.id != 29000022:
                    await channel.send(f"❌ Daily Summary: {player.name} is no longer in Legend League!")
                    continue

                # Handle case where daily_start_trophy is None
                start_trophies = channel_info.get("daily_start_trophy")
                if start_trophies is None:
                    start_trophies = 0
                    print(f"No start trophies found for {player.name}, using 0 until next reset")

                trophy_change = player.trophies - start_trophies

                embed = disnake.Embed(
                    title="📊 Daily Trophy Summary",
                    description=f"Summary for {player.name}",
                    color=disnake.Color.blue()
                )

                # Add note if this was the first summary
                if channel_info.get("daily_start_trophy") is None:
                    embed.add_field(
                        name="Note",
                        value="⚠️ This is the first summary for this player. Full trophy tracking will begin at next 10 PM reset.",
                        inline=False
                    )

                embed.add_field(
                    name="Trophy Change",
                    value=f"{'🔺' if trophy_change >= 0 else '🔻'} {trophy_change:+d}",
                    inline=False
                )

                embed.add_field(name="Starting Trophies", value=f"🏆 {start_trophies}", inline=True)
                embed.add_field(name="Current Trophies", value=f"🏆 {player.trophies}", inline=True)

                if player.clan:
                    embed.add_field(name="Clan", value=f"{player.clan.name}", inline=True)

                if player.league and player.league.icon:
                    embed.set_thumbnail(url=player.league.icon.url)

                embed.timestamp = current_time

                await channel.send(embed=embed)
                print(f"Sent daily summary for {player.name}")

                # Update daily start trophies only at exactly 10 PM
                if current_time.hour == 22 and current_time.minute == 0:
                    await update_trophy_count(tag, player.trophies, is_daily=True)
                else:
                    await update_trophy_count(tag, 0, is_daily=True)
                # if current_time.hour == 17 and current_time.minute == 50:
                #     await update_trophy_count(tag, player.trophies, is_daily=True)
                # else:
                #     await update_trophy_count(tag, 0, is_daily=True)

            except Exception as e:
                print(f"Error generating summary for channel {channel_info['channel_id']}: {e}")
                # Add more detailed error logging
                print(f"Channel info: {channel_info}")
                print(f"Current time: {current_time}")
                if 'player' in locals():
                    print(f"Player info: {player.__dict__}")


def setup(bot):
    bot.add_cog(PlayerCommands(bot))