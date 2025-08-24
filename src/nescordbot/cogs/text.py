"""Text message processing cog for Discord bot."""

import asyncio
import html
import logging
import re
from datetime import datetime
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ..services.note_processing import NoteProcessingService
from ..services.obsidian_github import ObsidianGitHubService

logger = logging.getLogger(__name__)

# Configuration constants
MAX_TEXT_LENGTH = 4000
VIEW_TIMEOUT = 300  # 5 minutes
NOTE_PATTERN = re.compile(r"^!note\s+(.+)", re.DOTALL | re.IGNORECASE)


class TextCog(commands.Cog):
    """Handle text message processing and conversion to Fleeting Notes."""

    def __init__(
        self,
        bot: commands.Bot,
        note_processing_service: Optional[NoteProcessingService] = None,
        obsidian_service: Optional[ObsidianGitHubService] = None,
    ):
        """Initialize the TextCog.

        Args:
            bot: The Discord bot instance
            note_processing_service: Service for AI text processing
            obsidian_service: Service for GitHub/Obsidian integration
        """
        self.bot = bot
        self.note_processing_service = note_processing_service
        self.obsidian_service = obsidian_service

        logger.info("TextCog initialized")
        if not self.note_processing_service:
            logger.warning("TextCog: NoteProcessingService not available")
        if not self.obsidian_service:
            logger.warning("TextCog: ObsidianGitHubService not available")

    async def handle_text_message(self, message: discord.Message, text: str) -> None:
        """Process text message and convert to Fleeting Note.

        Args:
            message: Discord message object
            text: Text content to process
        """
        try:
            # Validate and sanitize input
            if not text or not text.strip():
                await message.reply("❌ テキストを入力してください。")
                return

            # Sanitize input for security
            text = text.strip()

            # Check text length
            if len(text) > MAX_TEXT_LENGTH:
                await message.reply(f"❌ テキストが長すぎます（最大{MAX_TEXT_LENGTH}文字）。")
                return

            # Send initial response
            processing_msg = await message.reply("📝 テキストを処理中...")

            # Process with AI if service is available
            processed_text = text
            summary = ""

            if self.note_processing_service and self.note_processing_service.is_available():
                try:
                    result = await self.note_processing_service.process_text(
                        text, processing_type="fleeting_note"
                    )
                    processed_text = result.get("processed", text)
                    summary = result.get("summary", "")
                    logger.info("Text processed with NoteProcessingService")
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"AI service temporarily unavailable: {e}")
                    # Continue with original text if AI service is unavailable
                except ValueError as e:
                    logger.error(f"Invalid input for AI processing: {e}")
                    # Continue with original text if input is invalid
                except Exception as e:
                    logger.error(f"Unexpected error in AI processing: {e}")
                    # Continue with original text if AI processing fails

            # Format as Fleeting Note
            fleeting_note_content = self._format_fleeting_note(
                text=processed_text, summary=summary, message=message, note_type="text"
            )

            # Create view with save button
            view = FleetingNoteView(
                content=fleeting_note_content,
                summary=summary,
                obsidian_service=self.obsidian_service,
                note_type="text",
                message=message,
            )

            # Create embed for display
            embed = discord.Embed(
                title="📝 Fleeting Note",
                description=summary[:200] + "..." if len(summary) > 200 else summary,
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="処理済みテキスト",
                value=processed_text[:500] + "..." if len(processed_text) > 500 else processed_text,
                inline=False,
            )
            embed.set_footer(text=f"作成者: {message.author.name}")

            # Update message with result
            await processing_msg.edit(content="✅ テキスト処理が完了しました！", embed=embed, view=view)

            logger.info(f"Text message processed successfully for user {message.author}")

        except Exception as e:
            logger.error(f"Error handling text message: {e}", exc_info=True)
            await message.reply("❌ エラーが発生しました。管理者にお問い合わせください。")

    def _format_fleeting_note(
        self, text: str, summary: str, message: discord.Message, note_type: str = "text"
    ) -> str:
        """Format text as Fleeting Note with YAML frontmatter.

        Args:
            text: Processed text content
            summary: Text summary
            message: Discord message object for metadata
            note_type: Type of note (text/voice)

        Returns:
            Formatted Fleeting Note content
        """
        now = datetime.now()
        note_id = now.strftime("%Y%m%d%H%M%S")
        created_date = now.strftime("%Y-%m-%d %H:%M")

        # Build YAML frontmatter (safely escaped)
        safe_summary = html.escape(str(summary[:50] + "..." if len(summary) > 50 else summary))

        frontmatter = f"""---
id: {note_id}
title: "{safe_summary}"
type: fleeting_note
status: fleeting
created: {created_date}
---"""

        # Build note content
        content = f"""
# {summary[:100] if summary else "Fleeting Note"}

## 💭 アイデア・思考の断片
{text}

## 🔗 関連しそうなこと
-

## ❓ 疑問・調べたいこと
-

## 📝 次のアクション
- [ ] Literature Noteに発展させる
- [ ] Permanent Noteに昇華する
- [ ] 関連資料を調査する
- [ ] アーカイブする

---
*素早く記録することを優先。後で整理・発展させる。*
"""

        return frontmatter + content

    def _sanitize_username(self, username: str) -> str:
        """Sanitize username for file naming.

        Args:
            username: Raw username

        Returns:
            Sanitized username safe for file names
        """
        # Remove special characters and spaces
        sanitized = re.sub(r"[^\w\s-]", "", username)
        # Replace spaces with underscores
        sanitized = re.sub(r"\s+", "_", sanitized)
        # Limit length
        return sanitized[:20]

    @app_commands.command(name="note", description="テキストをFleeting Noteに変換して保存")
    @app_commands.describe(text=f"変換するテキスト（最大{MAX_TEXT_LENGTH}文字）")
    async def note_command(
        self, interaction: discord.Interaction, text: app_commands.Range[str, 1, 4000]
    ) -> None:
        """Slash command handler for creating Fleeting Notes.

        Args:
            interaction: Discord interaction
            text: Text to convert (1-4000 characters)
        """
        try:
            # Defer response for processing
            await interaction.response.defer()

            # Process with AI if available
            processed_text = text
            summary = ""

            if self.note_processing_service and self.note_processing_service.is_available():
                try:
                    result = await self.note_processing_service.process_text(
                        text, processing_type="fleeting_note"
                    )
                    processed_text = result.get("processed", text)
                    summary = result.get("summary", "")
                    logger.info("Text processed with NoteProcessingService for slash command")
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"AI service temporarily unavailable in slash command: {e}")
                except ValueError as e:
                    logger.error(f"Invalid input for AI processing in slash command: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in AI processing for slash command: {e}")

            # Create a pseudo-message object for formatting
            # This is needed because slash commands don't have a message object
            class PseudoMessage:
                def __init__(self, interaction: discord.Interaction):
                    self.author = interaction.user
                    self.guild = interaction.guild
                    self.channel = interaction.channel
                    self.id = interaction.id

            pseudo_message = PseudoMessage(interaction)  # type: ignore

            # Format as Fleeting Note
            fleeting_note_content = self._format_fleeting_note(
                text=processed_text,
                summary=summary,
                message=pseudo_message,  # type: ignore
                note_type="text",
            )

            # Create view with save button
            view = FleetingNoteView(
                content=fleeting_note_content,
                summary=summary,
                obsidian_service=self.obsidian_service,
                note_type="text",
                message=pseudo_message,  # type: ignore
            )

            # Create embed for display
            embed = discord.Embed(
                title="📝 Fleeting Note",
                description=summary[:200] + "..." if len(summary) > 200 else summary,
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="処理済みテキスト",
                value=processed_text[:500] + "..." if len(processed_text) > 500 else processed_text,
                inline=False,
            )
            embed.set_footer(text=f"作成者: {interaction.user.name}")

            # Send response
            await interaction.followup.send(
                content="✅ Fleeting Noteを作成しました！", embed=embed, view=view
            )

            logger.info(f"Slash command /note executed successfully by {interaction.user}")

        except Exception as e:
            logger.error(f"Error in /note command: {e}", exc_info=True)
            await interaction.followup.send("❌ エラーが発生しました。もう一度お試しください。", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages with !note prefix.

        Args:
            message: Discord message
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Check for !note prefix using regex for better efficiency
        if match := NOTE_PATTERN.match(message.content):
            text = match.group(1).strip()
            if text:
                await self.handle_text_message(message, text)


class FleetingNoteView(discord.ui.View):
    """View for Fleeting Note with save button."""

    def __init__(
        self,
        content: str,
        summary: str,
        obsidian_service: Optional[ObsidianGitHubService],
        note_type: str = "voice",
        message: Optional[discord.Message] = None,
    ):
        """Initialize the view.

        Args:
            content: Fleeting Note content
            summary: Note summary
            obsidian_service: ObsidianGitHub service
            note_type: Type of note (text/voice)
            message: Original Discord message
        """
        super().__init__(timeout=VIEW_TIMEOUT)
        self.content = content
        self.summary = summary
        self.obsidian_service = obsidian_service
        self.note_type = note_type
        self.message = message

    def _generate_filename(self, user_name: str) -> str:
        """Generate filename following vault specification.

        Args:
            user_name: Discord username

        Returns:
            Formatted filename
        """
        now = datetime.now()
        date_time = now.strftime("%Y%m%d_%H%M")

        # Sanitize username
        sanitized_name = re.sub(r"[^\w\s-]", "", user_name)
        sanitized_name = re.sub(r"\s+", "_", sanitized_name)[:20]

        return f"{date_time}_discord_{self.note_type}_{sanitized_name}.md"

    @discord.ui.button(label="Obsidianに保存", style=discord.ButtonStyle.primary, emoji="📝")
    async def save_to_obsidian(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save Fleeting Note to Obsidian via GitHub.

        Args:
            interaction: Discord interaction
            button: Button that was clicked
        """
        try:
            if not self.obsidian_service:
                await interaction.response.send_message(
                    "❌ Obsidian保存サービスが利用できません。\n"
                    "管理者に設定確認を依頼してください。\n"
                    "詳細: `/debug config` コマンドで診断可能",
                    ephemeral=True,
                )
                return

            # Defer response
            await interaction.response.defer(ephemeral=True)

            # Generate filename
            filename = self._generate_filename(interaction.user.name)

            # Save to GitHub queue
            try:
                request_id = await self.obsidian_service.save_to_obsidian(
                    filename=filename,
                    content=self.content,
                    directory="Fleeting Notes",
                    metadata={
                        "type": "fleeting_note",
                        "note_type": self.note_type,
                        "discord_user": str(interaction.user),
                        "discord_channel": str(interaction.channel),
                        "created_at": datetime.now().isoformat(),
                    },
                )

                # Send initial queued message
                await interaction.followup.send(
                    f"📝 Fleeting Noteを処理キューに追加しました\n"
                    f"📁 `Fleeting Notes/{filename}`\n"
                    f"⏳ GitHub保存処理中...\n"
                    f"📍 リクエストID: `{request_id[:8]}`",
                    ephemeral=True,
                )

                # Disable button after successful queue addition
                button.disabled = True
                if interaction.message:
                    await interaction.message.edit(view=self)

                logger.info(
                    f"Fleeting Note queued for processing: {filename} (request_id: {request_id})"
                )

                # Optional: Wait briefly and check processing status
                try:
                    import asyncio

                    await asyncio.sleep(2.0)  # Wait for potential immediate processing

                    status = await self.obsidian_service.get_status(request_id)
                    if status and status.status != "queued":
                        # Send status update if processing started
                        status_emoji = (
                            "✅"
                            if status.status == "completed"
                            else "⚠️"
                            if status.status == "failed"
                            else "🔄"
                        )
                        status_msg = {
                            "completed": "GitHub保存が完了しました",
                            "failed": "GitHub保存に失敗しました",
                            "processing": "GitHub保存処理中です",
                        }.get(status.status, f"処理状況: {status.status}")

                        await interaction.followup.send(
                            f"{status_emoji} {status_msg}\n" f"📁 `{status.file_path}`",
                            ephemeral=True,
                        )
                except Exception as status_check_error:
                    # Status check is optional, don't fail the main process
                    logger.debug(f"Status check failed (non-critical): {status_check_error}")

            except Exception as e:
                logger.error(f"Error queuing Obsidian save: {e}")
                await interaction.followup.send(
                    f"❌ 保存キューへの追加中にエラーが発生しました: {str(e)}\n" f"💡 `/debug config` でサービス状態を確認してください",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in save_to_obsidian button: {e}", exc_info=True)
            try:
                await interaction.followup.send("❌ エラーが発生しました。", ephemeral=True)
            except Exception:
                # If followup fails too, at least log the error
                logger.error("Failed to send error message to user")


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot.

    Args:
        bot: The Discord bot instance
    """
    # Get services from bot if available
    note_processing_service = getattr(bot, "note_processing_service", None)
    obsidian_service = getattr(bot, "obsidian_service", None)

    # Create and add the cog
    await bot.add_cog(TextCog(bot, note_processing_service, obsidian_service))
    logger.info("TextCog loaded")
