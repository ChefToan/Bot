import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import logging
from typing import Dict, List


class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.playing_tracks: Dict[int, wavelink.Playable] = {}
        self.queues: Dict[int, List[wavelink.Playable]] = {}

    music = app_commands.Group(name="music", description="Music commands")

    @music.command(name="play", description="Play a song from YouTube/Spotify")
    @app_commands.describe(query="The song to play (YouTube/Spotify URL or search query)")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if not interaction.user.voice:
            await interaction.response.send_message("You need to be in a voice channel!")
            return

        # Ensure bot can join the voice channel
        if not interaction.guild.voice_client:
            try:
                await interaction.user.voice.channel.connect(cls=wavelink.Player)
            except Exception as e:
                await interaction.response.send_message(f"Could not join voice channel: {str(e)}")
                return

        # Get the player
        player: wavelink.Player = interaction.guild.voice_client

        # Search for the track
        try:
            await interaction.response.defer()

            # Handle different types of queries
            if 'spotify.com' in query:
                # Handle Spotify URLs using lavasrc plugin
                decoded = await wavelink.Playable.search(query)
            else:
                # Use YouTube search
                decoded = await wavelink.Playable.search(query)

            if not decoded:
                await interaction.followup.send("No tracks found!")
                return

            track = decoded[0]

            # If a track is already playing, add to queue
            if player.playing:
                if interaction.guild_id not in self.queues:
                    self.queues[interaction.guild_id] = []
                self.queues[interaction.guild_id].append(track)
                await interaction.followup.send(f"Added to queue: **{track.title}**")
            else:
                await player.play(track)
                self.playing_tracks[interaction.guild_id] = track
                await interaction.followup.send(f"Now playing: **{track.title}**")

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @music.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if interaction.guild_id not in self.queues or not self.queues[interaction.guild_id]:
            await interaction.response.send_message("The queue is empty!")
            return

        queue_list = "\n".join([f"{i + 1}. {track.title}" for i, track in enumerate(self.queues[interaction.guild_id])])
        await interaction.response.send_message(f"**Current Queue:**\n{queue_list}")

    @music.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if not interaction.guild.voice_client or not interaction.guild.voice_client.playing:
            await interaction.response.send_message("Nothing is playing!")
            return

        player: wavelink.Player = interaction.guild.voice_client
        await player.stop()
        await interaction.response.send_message("Skipped the current song!")

    @music.command(name="stop", description="Stop the music and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if not interaction.guild.voice_client:
            await interaction.response.send_message("I'm not playing anything!")
            return

        player: wavelink.Player = interaction.guild.voice_client

        # Clear queue
        if interaction.guild_id in self.queues:
            self.queues[interaction.guild_id].clear()

        await player.stop()
        await interaction.response.send_message("Stopped playing and cleared the queue!")

    @music.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if not interaction.guild.voice_client or not interaction.guild.voice_client.playing:
            await interaction.response.send_message("Nothing is playing!")
            return

        player: wavelink.Player = interaction.guild.voice_client

        if player.paused:
            await interaction.response.send_message("The player is already paused!")
            return

        await player.set_pause(True)
        await interaction.response.send_message("Paused the current song!")

    @music.command(name="resume", description="Resume the current song")
    async def resume(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if not interaction.guild.voice_client:
            await interaction.response.send_message("Nothing is paused!")
            return

        player: wavelink.Player = interaction.guild.voice_client

        if not player.paused:
            await interaction.response.send_message("The player is not paused!")
            return

        await player.set_pause(False)
        await interaction.response.send_message("Resumed the current song!")

    @music.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if interaction.guild_id not in self.playing_tracks:
            await interaction.response.send_message("Nothing is playing!")
            return

        track = self.playing_tracks[interaction.guild_id]
        await interaction.response.send_message(f"Now playing: **{track.title}**")

    @music.command(name="disconnect", description="Disconnect the bot from voice")
    async def disconnect(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!")
            return

        if not interaction.guild.voice_client:
            await interaction.response.send_message("I'm not in a voice channel!")
            return

        # Clear queue and playing track
        if interaction.guild_id in self.queues:
            self.queues[interaction.guild_id].clear()
        if interaction.guild_id in self.playing_tracks:
            del self.playing_tracks[interaction.guild_id]

        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Disconnected from voice channel!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        try:
            # Check if player and guild exist
            if not payload.player or not payload.player.guild:
                return

            guild_id = payload.player.guild.id

            # Remove the finished track
            if guild_id in self.playing_tracks:
                del self.playing_tracks[guild_id]

            # Play next song in queue if available
            if guild_id in self.queues and self.queues[guild_id]:
                try:
                    next_track = self.queues[guild_id].pop(0)
                    await payload.player.play(next_track)
                    self.playing_tracks[guild_id] = next_track
                except Exception as e:
                    logging.error(f"Error playing next track: {e}")

        except Exception as e:
            logging.error(f"Error in track_end event: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        try:
            if payload.player and payload.player.guild:
                guild_id = payload.player.guild.id
                if guild_id in self.playing_tracks:
                    del self.playing_tracks[guild_id]

                # Try to play next song if available
                if guild_id in self.queues and self.queues[guild_id]:
                    try:
                        next_track = self.queues[guild_id].pop(0)
                        await payload.player.play(next_track)
                        self.playing_tracks[guild_id] = next_track
                    except Exception as e:
                        logging.error(f"Error playing next track after exception: {e}")
        except Exception as e:
            logging.error(f"Error in track_exception event: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        logging.info(f"Wavelink node '{payload.node.identifier}' is ready!")


async def setup(bot):
    await bot.add_cog(MusicCommands(bot))