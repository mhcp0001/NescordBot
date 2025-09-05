"""Text message processing cog for Discord bot."""

import asyncio
import html
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ..services.note_processing import NoteProcessingService
from ..services.obsidian_github import ObsidianGitHubService

if TYPE_CHECKING:
    from ..services.knowledge_manager import KnowledgeManager

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
        knowledge_manager: Optional["KnowledgeManager"] = None,
    ):
        """Initialize the TextCog.

        Args:
            bot: The Discord bot instance
            note_processing_service: Service for AI text processing
            obsidian_service: Service for GitHub/Obsidian integration
            knowledge_manager: Service for PKM functionality
        """
        self.bot = bot
        self.note_processing_service = note_processing_service
        self.obsidian_service = obsidian_service
        self.knowledge_manager = knowledge_manager

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
                knowledge_manager=self.knowledge_manager,
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
                knowledge_manager=self.knowledge_manager,
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
        knowledge_manager: Optional["KnowledgeManager"] = None,
        note_type: str = "voice",
        message: Optional[discord.Message] = None,
    ):
        """Initialize the view.

        Args:
            content: Fleeting Note content
            summary: Note summary
            obsidian_service: ObsidianGitHub service
            knowledge_manager: KnowledgeManager for PKM functionality
            note_type: Type of note (text/voice)
            message: Original Discord message
        """
        super().__init__(timeout=VIEW_TIMEOUT)
        self.content = content
        self.summary = summary
        self.obsidian_service = obsidian_service
        self.knowledge_manager = knowledge_manager
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

    @discord.ui.button(label="PKMに保存", style=discord.ButtonStyle.success, emoji="🧠")
    async def save_to_pkm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save Fleeting Note to PKM system with auto-tagging.

        Args:
            interaction: Discord interaction
            button: Button that was clicked
        """
        logger = logging.getLogger(__name__)

        try:
            if not self.knowledge_manager:
                await interaction.response.send_message(
                    "❌ PKMサービスが利用できません。\n" "管理者に設定確認を依頼してください。",
                    ephemeral=True,
                )
                return

            # Defer response for processing
            await interaction.response.defer(ephemeral=True)

            # Generate note title from summary
            title = self.summary[:50].strip() if self.summary else f"Discord {self.note_type} note"
            if len(title) < len(self.summary):
                title += "..."

            try:
                # Auto-suggest tags using KnowledgeManager
                tag_suggestions = await self.knowledge_manager.suggest_tags_for_content(
                    content=self.content, title=title, max_suggestions=5
                )

                # Extract high-confidence tags (>0.8)
                auto_tags = [
                    suggestion["tag"]
                    for suggestion in tag_suggestions
                    if suggestion["confidence"] > 0.8
                ]

                # Ensure we have at least basic tags
                if not auto_tags:
                    auto_tags = ["fleeting-note", self.note_type]
                elif "fleeting-note" not in auto_tags:
                    auto_tags.append("fleeting-note")

                logger.info(f"Auto-generated tags for PKM: {auto_tags}")

                # Create note in PKM system
                note_id = await self.knowledge_manager.create_note(
                    title=title,
                    content=self.content,
                    tags=auto_tags,
                    source_type="discord",
                    source_id=str(self.message.id) if self.message else None,
                    user_id=str(interaction.user.id),
                    channel_id=str(interaction.channel.id) if interaction.channel else None,
                    guild_id=str(interaction.guild.id) if interaction.guild else None,
                )

                # Search for related notes
                related_notes = []
                try:
                    search_results = await self.knowledge_manager.search_notes(query=title, limit=4)
                    # Filter out the just-created note
                    related_notes = [note for note in search_results if note.get("id") != note_id][
                        :3
                    ]  # Limit to 3 related notes
                except Exception as e:
                    logger.warning(f"Related notes search failed: {e}")

                # Build response message
                response_parts = [
                    "🧠 **PKMノートを作成しました！**",
                    f"📝 **タイトル**: {title}",
                    f"🏷️ **タグ**: {', '.join(auto_tags)}",
                    f"🆔 **ノートID**: `{note_id}`",
                ]

                if related_notes:
                    response_parts.append("\n🔗 **関連ノート**:")
                    for i, note in enumerate(related_notes[:3], 1):
                        note_title = note.get("title", "無題")[:30]
                        score = note.get("score", 0)
                        response_parts.append(f"{i}. {note_title} (類似度: {score:.2f})")

                # Suggest additional tags
                suggested_tags = [
                    suggestion["tag"]
                    for suggestion in tag_suggestions
                    if suggestion["confidence"] <= 0.8 and suggestion["confidence"] > 0.5
                ]
                if suggested_tags:
                    response_parts.append(f"\n💡 **追加タグ候補**: {', '.join(suggested_tags[:3])}")

                await interaction.followup.send("\n".join(response_parts), ephemeral=True)

                # Disable button after successful save
                button.disabled = True
                if interaction.message:
                    await interaction.message.edit(view=self)

                logger.info(f"PKM note created successfully: {note_id}")

            except Exception as e:
                logger.error(f"Error creating PKM note: {e}")
                await interaction.followup.send(
                    f"❌ PKMノートの作成中にエラーが発生しました: {str(e)}\n" f"💡 管理者にお問い合わせください。",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in save_to_pkm button: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ エラーが発生しました。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ エラーが発生しました。", ephemeral=True)
            except Exception:
                logger.error("Failed to send error message to user")

    @discord.ui.button(label="🔗 関連ノート", style=discord.ButtonStyle.secondary)
    async def show_related_notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show related notes based on content."""
        logger = logging.getLogger(__name__)

        try:
            if not self.knowledge_manager:
                await interaction.response.send_message("❌ PKMサービスが利用できません。", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            # Search for related notes using content and summary
            search_query = f"{self.summary} {self.content[:200]}"  # Limit to avoid token limit

            try:
                related_notes = await self.knowledge_manager.search_notes(
                    query=search_query, limit=5
                )

                if not related_notes:
                    await interaction.followup.send("🔍 関連するノートが見つかりませんでした。", ephemeral=True)
                    return

                # Build response with related notes
                response_parts = [f"🔗 **関連ノート ({len(related_notes)}件)**\n"]

                for i, note in enumerate(related_notes, 1):
                    note_title = note.get("title", "無題")[:40]
                    note_tags = note.get("tags", [])
                    created_at = note.get("created_at", "")

                    # Format creation date
                    date_str = ""
                    if created_at:
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            date_str = f" ({dt.strftime('%m-%d')})"
                        except Exception:
                            pass

                    # Show tags if available
                    tag_str = ""
                    if note_tags and isinstance(note_tags, list):
                        tag_str = f" `{', '.join(note_tags[:3])}`"

                    response_parts.append(f"{i}. **{note_title}**{date_str}{tag_str}")

                    # Add a brief content preview
                    content_preview = note.get("content", "")[:80]
                    if content_preview:
                        response_parts.append(f"   _{content_preview}..._")

                # Add search tips
                response_parts.append("\n💡 **ヒント**: `/pkm search <キーワード>` で詳細検索が可能です")

                await interaction.followup.send("\n".join(response_parts), ephemeral=True)

            except Exception as e:
                logger.error(f"Error searching related notes: {e}")
                await interaction.followup.send("❌ 関連ノート検索中にエラーが発生しました。", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in show_related_notes: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ エラーが発生しました。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ エラーが発生しました。", ephemeral=True)
            except Exception:
                logger.error("Failed to send error message to user")

    @discord.ui.button(label="🔄 Permanent化", style=discord.ButtonStyle.success, row=1)
    async def convert_to_permanent(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Convert Fleeting Note to Permanent Note with expanded content."""
        logger = logging.getLogger(__name__)

        try:
            if not self.knowledge_manager:
                await interaction.response.send_message("❌ PKMサービスが利用できません。", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            try:
                # Generate expanded content using AI
                expanded_content = await self._generate_expanded_content()

                if not expanded_content:
                    await interaction.followup.send("❌ コンテンツの拡張に失敗しました。", ephemeral=True)
                    return

                # Suggest permanent tags (remove fleeting-note, add structured tags)
                permanent_tags = await self._generate_permanent_tags()

                # Create permanent note
                permanent_title = f"[Permanent] {self.summary[:40]}"

                permanent_note_id = await self.knowledge_manager.create_note(
                    title=permanent_title,
                    content=expanded_content,
                    tags=permanent_tags,
                    source_type="permanent_conversion",
                    source_id=str(self.message.id) if self.message else None,
                    user_id=str(interaction.user.id),
                    channel_id=str(interaction.channel.id) if interaction.channel else None,
                    guild_id=str(interaction.guild.id) if interaction.guild else None,
                )

                # Build success response
                response_parts = [
                    "✨ **Permanentノートを作成しました！**",
                    f"📝 **タイトル**: {permanent_title}",
                    f"🏷️ **新タグ**: {', '.join(permanent_tags)}",
                    f"🆔 **ノートID**: `{permanent_note_id}`",
                    "\n📈 **拡張内容**:",
                    "- 詳細な説明と文脈を追加",
                    "- 関連情報の整理",
                    "- アクションアイテムの抽出",
                    "\n💡 永続的な知識として体系化されました。",
                ]

                await interaction.followup.send("\n".join(response_parts), ephemeral=True)

                # Disable the button after successful conversion
                button.disabled = True
                button.label = "✅ Permanent化済み"
                if interaction.message:
                    await interaction.message.edit(view=self)

                logger.info(f"Fleeting note converted to permanent: {permanent_note_id}")

            except Exception as e:
                logger.error(f"Error converting to permanent note: {e}")
                await interaction.followup.send(
                    f"❌ Permanent変換中にエラーが発生しました: {str(e)}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in convert_to_permanent: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ エラーが発生しました。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ エラーが発生しました。", ephemeral=True)
            except Exception:
                logger.error("Failed to send error message to user")

    async def _generate_expanded_content(self) -> str:
        """Generate expanded content for permanent note using AI."""
        try:
            # Note: This would need to be implemented with actual AI service
            # For now, return a structured expansion
            expanded = f"""# {self.summary}

## 概要
{self.summary}

## 詳細
{self.content}

## 関連情報
このメモは Discord の {self.note_type} メッセージから作成されました。
詳細な文脈や関連情報の追加が推奨されます。

## アクションアイテム
- [ ] 詳細な調査や分析が必要な場合は追加検討
- [ ] 関連するノートとの連携を確認

## メタ情報
- 作成日: {datetime.now().strftime('%Y-%m-%d')}
- ソース: Discord Fleeting Note
- タイプ: {self.note_type}
- 変換日: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            return expanded

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating expanded content: {e}")
            return ""

    async def _generate_permanent_tags(self) -> List[str]:
        """Generate appropriate tags for permanent note."""
        try:
            # Remove fleeting-note tag and add permanent-note
            permanent_tags = ["permanent-note", "structured"]

            # Add type-specific tag
            if self.note_type:
                permanent_tags.append(f"{self.note_type}-converted")

            # Try to suggest additional tags based on content
            if self.knowledge_manager:
                try:
                    tag_suggestions = await self.knowledge_manager.suggest_tags_for_content(
                        content=self.content, title=self.summary, max_suggestions=3
                    )

                    # Add high-confidence tags
                    for suggestion in tag_suggestions:
                        if suggestion["confidence"] > 0.7:
                            tag = suggestion["tag"]
                            if tag not in permanent_tags and tag != "fleeting-note":
                                permanent_tags.append(tag)

                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to get tag suggestions: {e}")

            return permanent_tags[:6]  # Limit to 6 tags

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating permanent tags: {e}")
            return ["permanent-note", "structured"]


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot.

    Args:
        bot: The Discord bot instance
    """
    # Get services from bot if available
    note_processing_service = getattr(bot, "note_processing_service", None)
    obsidian_service = getattr(bot, "obsidian_service", None)
    knowledge_manager = getattr(bot, "knowledge_manager", None)

    # Create and add the cog
    await bot.add_cog(TextCog(bot, note_processing_service, obsidian_service, knowledge_manager))
    logger.info("TextCog loaded")
