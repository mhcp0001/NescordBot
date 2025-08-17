"""Obsidian integration commands for NescordBot."""

import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..services.obsidian import ObsidianService

logger = logging.getLogger(__name__)


class ObsidianCog(commands.Cog):
    """Cog for Obsidian vault integration commands."""

    def __init__(self, bot: commands.Bot, obsidian_service: Optional[ObsidianService] = None):
        """Initialize Obsidian cog.

        Args:
            bot: Discord bot instance
            obsidian_service: Obsidian service instance
        """
        self.bot = bot
        self.obsidian_service = obsidian_service

    @app_commands.command(
        name="obsidian-save-message", description="Save a Discord message to Obsidian vault"
    )
    @app_commands.describe(
        message_id="ID of the message to save",
        title="Custom title for the note (optional)",
        tags="Comma-separated tags (optional)",
    )
    async def save_message(
        self,
        interaction: discord.Interaction,
        message_id: str,
        title: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> None:
        """Save a Discord message to Obsidian vault.

        Args:
            interaction: Discord interaction
            message_id: Message ID to save
            title: Optional custom title
            tags: Optional comma-separated tags
        """
        if not self.obsidian_service or not self.obsidian_service.is_initialized:
            await interaction.response.send_message(
                "❌ Obsidian integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get the message
            if not interaction.channel:
                raise ValueError("Channel not found")
            message = await interaction.channel.fetch_message(int(message_id))  # type: ignore[union-attr]

            # Parse tags
            tag_list = [tag.strip() for tag in tags.split(",")] if tags else None

            # Save to Obsidian
            file_path = await self.obsidian_service.save_message(
                message=message,
                title=title,
                tags=tag_list,
            )

            # Create embed response
            embed = discord.Embed(
                title="✅ Message Saved to Obsidian",
                description=f"Message from {message.author.mention} has been saved.",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="File",
                value=f"`{file_path.name}`",
                inline=False,
            )
            embed.add_field(
                name="Location",
                value=f"`{file_path.parent.relative_to(self.obsidian_service.vault_path)}`",  # type: ignore[arg-type]
                inline=True,
            )
            if tag_list:
                embed.add_field(
                    name="Tags",
                    value=", ".join(f"`{tag}`" for tag in tag_list),
                    inline=True,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Message saved to Obsidian by {interaction.user}")

        except discord.NotFound:
            await interaction.followup.send(
                "❌ Message not found. Please check the message ID.", ephemeral=True
            )
        except ValueError:
            await interaction.followup.send(
                "❌ Invalid message ID. Please provide a valid numeric ID.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to save message to Obsidian: {e}")
            await interaction.followup.send(f"❌ Failed to save message: {str(e)}", ephemeral=True)

    @app_commands.command(
        name="obsidian-save-voice", description="Save voice transcription to Obsidian vault"
    )
    @app_commands.describe(
        transcription="The transcribed text",
        duration="Duration of the voice message in seconds",
        tags="Comma-separated tags (optional)",
    )
    async def save_voice_transcription(
        self,
        interaction: discord.Interaction,
        transcription: str,
        duration: Optional[float] = None,
        tags: Optional[str] = None,
    ) -> None:
        """Save voice transcription to Obsidian vault.

        Args:
            interaction: Discord interaction
            transcription: Transcribed text
            duration: Optional duration in seconds
            tags: Optional comma-separated tags
        """
        if not self.obsidian_service or not self.obsidian_service.is_initialized:
            await interaction.response.send_message(
                "❌ Obsidian integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Parse tags
            tag_list = [tag.strip() for tag in tags.split(",")] if tags else None

            # Save to Obsidian
            file_path = await self.obsidian_service.save_voice_transcription(
                transcription=transcription,
                user=interaction.user,
                channel=interaction.channel,  # type: ignore[arg-type]
                duration=duration,
                tags=tag_list,
            )

            # Create embed response
            embed = discord.Embed(
                title="🎤 Voice Transcription Saved",
                description="Voice transcription has been saved to Obsidian.",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="File",
                value=f"`{file_path.name}`",
                inline=False,
            )
            if duration:
                embed.add_field(
                    name="Duration",
                    value=f"{duration:.1f} seconds",
                    inline=True,
                )
            embed.add_field(
                name="Transcript Length",
                value=f"{len(transcription)} characters",
                inline=True,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Voice transcription saved to Obsidian by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to save voice transcription: {e}")
            await interaction.followup.send(
                f"❌ Failed to save transcription: {str(e)}", ephemeral=True
            )

    @app_commands.command(
        name="obsidian-daily-note", description="Create or append to today's daily note"
    )
    @app_commands.describe(
        content="Content to add to the daily note (optional)",
    )
    async def create_daily_note(
        self,
        interaction: discord.Interaction,
        content: Optional[str] = None,
    ) -> None:
        """Create or append to daily note.

        Args:
            interaction: Discord interaction
            content: Optional content to add
        """
        if not self.obsidian_service or not self.obsidian_service.is_initialized:
            await interaction.response.send_message(
                "❌ Obsidian integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Create or update daily note
            file_path = await self.obsidian_service.create_daily_note(content=content)

            # Create embed response
            embed = discord.Embed(
                title="📅 Daily Note Updated",
                description=(
                    f"Daily note for {datetime.now().strftime('%Y-%m-%d')} " "has been updated."
                ),
                color=discord.Color.purple(),
            )
            embed.add_field(
                name="File",
                value=f"`{file_path.name}`",
                inline=False,
            )
            if content:
                preview = content[:100] + "..." if len(content) > 100 else content
                embed.add_field(
                    name="Added Content",
                    value=f"```{preview}```",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Daily note updated by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to create/update daily note: {e}")
            await interaction.followup.send(
                f"❌ Failed to update daily note: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="obsidian-search", description="Search notes in Obsidian vault")
    @app_commands.describe(
        query="Search query",
        folder="Specific folder to search in (optional)",
        limit="Maximum number of results (1-20)",
    )
    async def search_notes(
        self,
        interaction: discord.Interaction,
        query: str,
        folder: Optional[str] = None,
        limit: int = 10,
    ) -> None:
        """Search notes in Obsidian vault.

        Args:
            interaction: Discord interaction
            query: Search query
            folder: Optional folder to search in
            limit: Maximum results
        """
        if not self.obsidian_service or not self.obsidian_service.is_initialized:
            await interaction.response.send_message(
                "❌ Obsidian integration is not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        try:
            # Validate limit
            limit = min(max(1, limit), 20)

            # Search notes
            results = await self.obsidian_service.search_notes(
                query=query,
                folder=folder,
                limit=limit,
            )

            if not results:
                await interaction.followup.send(f"No results found for query: `{query}`")
                return

            # Create embed
            embed = discord.Embed(
                title=f"🔍 Search Results for: {query}",
                description=f"Found {len(results)} matching notes",
                color=discord.Color.blue(),
            )

            for file_path, excerpt in results[:10]:  # Limit display to 10
                # Get relative path
                try:
                    rel_path = file_path.relative_to(self.obsidian_service.vault_path)  # type: ignore[arg-type]
                except ValueError:
                    rel_path = file_path

                # Truncate excerpt if needed
                if len(excerpt) > 200:
                    excerpt = excerpt[:200] + "..."

                embed.add_field(
                    name=f"📄 {file_path.stem}",
                    value=f"`{rel_path}`\n```{excerpt}```",
                    inline=False,
                )

            embed.set_footer(text=f"Showing {min(10, len(results))} of {len(results)} results")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to search notes: {e}")
            await interaction.followup.send(f"❌ Failed to search notes: {str(e)}", ephemeral=True)

    @app_commands.command(name="obsidian-status", description="Check Obsidian integration status")
    async def check_status(self, interaction: discord.Interaction) -> None:
        """Check Obsidian integration status.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.obsidian_service:
                status = "❌ Not Configured"
                vault_path = "N/A"
                initialized = False
            else:
                initialized = self.obsidian_service.is_initialized
                status = "✅ Active" if initialized else "⚠️ Not Initialized"
                vault_path = (
                    str(self.obsidian_service.vault_path)  # type: ignore[union-attr]
                    if self.obsidian_service.vault_path  # type: ignore[union-attr]
                    else "Not Set"
                )

            # Create embed
            embed = discord.Embed(
                title="📚 Obsidian Integration Status",
                color=discord.Color.green() if initialized else discord.Color.orange(),
            )

            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Vault Path", value=f"`{vault_path}`", inline=False)

            if initialized and self.obsidian_service.vault_path:
                # Count files in vault
                try:
                    md_files = list(self.obsidian_service.vault_path.rglob("*.md"))  # type: ignore[union-attr]
                    folders = ["messages", "voice", "github", "daily", "attachments"]
                    folder_stats = []
                    for folder in folders:
                        folder_path = self.obsidian_service.vault_path / folder
                        if folder_path.exists():
                            count = len(list(folder_path.glob("*")))
                            folder_stats.append(f"`{folder}`: {count} files")

                    embed.add_field(
                        name="Vault Statistics",
                        value=f"Total markdown files: {len(md_files)}",
                        inline=False,
                    )
                    if folder_stats:
                        embed.add_field(
                            name="Folder Contents",
                            value="\n".join(folder_stats),
                            inline=False,
                        )
                except Exception as e:
                    logger.debug(f"Could not get vault statistics: {e}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to check status: {e}")
            await interaction.followup.send(f"❌ Failed to check status: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Set up the Obsidian cog.

    Args:
        bot: Discord bot instance
    """
    # Try to get Obsidian service from bot
    obsidian_service = None
    if hasattr(bot, "obsidian_service"):
        obsidian_service = bot.obsidian_service

    await bot.add_cog(ObsidianCog(bot, obsidian_service))
    logger.info("Obsidian cog loaded")
