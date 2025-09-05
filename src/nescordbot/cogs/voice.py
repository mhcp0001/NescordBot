import io
import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands
from openai import OpenAI

from ..services import NoteProcessingService, ObsidianGitHubService

if TYPE_CHECKING:
    from ..services.knowledge_manager import KnowledgeManager


class Voice(commands.Cog):
    """音声処理関連のコマンドを管理するCog"""

    def __init__(
        self,
        bot,
        obsidian_service: Optional[ObsidianGitHubService] = None,
        note_processing_service: Optional[NoteProcessingService] = None,
        knowledge_manager: Optional["KnowledgeManager"] = None,
    ):
        self.bot = bot
        self.obsidian_service = obsidian_service
        self.note_processing_service = note_processing_service
        self.knowledge_manager = knowledge_manager

        # TranscriptionServiceを初期化
        from ..services.transcription import get_transcription_service

        self.transcription_service = get_transcription_service()

        # 後方互換性のためにopenai_clientも保持（setup_openaiで初期化）
        self.openai_client: Optional[OpenAI] = None
        self.setup_openai()

    def setup_openai(self):
        """OpenAI APIの設定"""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
        else:
            logging.getLogger(__name__).warning("OpenAI APIキーが設定されていません")

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """音声ファイルを文字起こし（TranscriptionServiceを使用）"""
        if not self.transcription_service.is_available():
            logging.getLogger(__name__).warning(
                f"TranscriptionService ({self.transcription_service.provider_name}) が利用できません"
            )
            return None

        try:
            result = await self.transcription_service.transcribe(audio_path)
            if result:
                logging.getLogger(__name__).info(
                    f"文字起こし完了 (プロバイダー: {self.transcription_service.provider_name}): "
                    f"{len(result)}文字"
                )
            return result
        except Exception as e:
            logging.getLogger(__name__).error(f"TranscriptionService文字起こしエラー: {e}")
            return None

    async def process_with_ai(self, text: str) -> dict:
        """AIで文字起こし結果を処理（NoteProcessingServiceに委譲）"""
        logger = logging.getLogger(__name__)

        if self.note_processing_service and self.note_processing_service.is_available():
            try:
                logger.info("NoteProcessingServiceで音声テキスト処理を開始")
                result = await self.note_processing_service.process_text(
                    text, processing_type="voice_transcription"
                )
                logger.info("NoteProcessingServiceでの処理が完了")
                return result
            except Exception as e:
                logger.error(f"NoteProcessingService処理エラー: {e}")
                # フォールバックに移行
                pass

        # フォールバック: サービスが利用できない場合
        logger.warning("NoteProcessingService利用不可、フォールバック処理を実行")
        return {"processed": text, "summary": "AI処理サービスが利用できないため、元のテキストをそのまま表示します"}

    @app_commands.command(name="transcribe", description="音声ファイルを文字起こしします")
    async def transcribe_command(self, interaction: discord.Interaction):
        """手動文字起こしコマンド"""
        await interaction.response.send_message(
            "音声ファイルを含むメッセージに返信する形で、このコマンドを使用してください。", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        """メッセージイベントの処理"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # 音声ファイルの自動処理
        for attachment in message.attachments:
            if attachment.content_type and "audio" in attachment.content_type:
                await self.handle_voice_message(message, attachment)

    async def handle_voice_message(self, message: discord.Message, attachment: discord.Attachment):
        """音声メッセージの処理"""
        logger = logging.getLogger(__name__)
        start_time = time.time()
        temp_path = None

        try:
            # ファイルサイズチェック
            max_size = 25 * 1024 * 1024  # 25MB
            if attachment.size > max_size:
                await message.reply(
                    f"❌ ファイルサイズが大きすぎます（最大: 25MB、現在: {attachment.size / 1024 / 1024:.1f}MB）"
                )
                return

            logger.info(
                f"音声処理開始: ユーザー={message.author}, ファイル={attachment.filename}, サイズ={attachment.size}B"
            )

            # 処理中の表示
            processing_msg = await message.reply("🎤 音声を処理しています...")

            # 音声ファイルをダウンロード
            audio_data = await attachment.read()
            temp_path = os.path.join("data", f"temp_{message.id}.ogg")
            os.makedirs("data", exist_ok=True)

            with open(temp_path, "wb") as f:
                f.write(audio_data)

            # 文字起こし
            transcription_start = time.time()
            transcription = await self.transcribe_audio(temp_path)
            transcription_time = time.time() - transcription_start

            logger.info(
                f"音声認識完了: 時間={transcription_time:.2f}秒, "
                f"文字数={len(transcription) if transcription else 0}"
            )

            if transcription:
                # AI処理
                ai_start = time.time()
                ai_result = await self.process_with_ai(transcription)
                ai_time = time.time() - ai_start

                logger.info(f"AI処理完了: 時間={ai_time:.2f}秒")

                # 結果をEmbedで表示
                embed = discord.Embed(
                    title="🎤 音声メッセージの文字起こし",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow(),
                )

                embed.add_field(name="📝 要約", value=ai_result["summary"], inline=False)

                # 長いテキストは分割
                processed_text = ai_result["processed"]
                if len(processed_text) > 1024:
                    embed.add_field(
                        name="✨ 整形済みテキスト（一部）", value=processed_text[:1021] + "...", inline=False
                    )
                    # 全文はファイルで添付
                    full_text_bytes = processed_text.encode("utf-8")
                    file = discord.File(
                        io.BytesIO(full_text_bytes), filename=f"transcription_{message.id}.txt"
                    )
                    await processing_msg.edit(content=None, embed=embed, attachments=[file])
                else:
                    embed.add_field(name="✨ 整形済みテキスト", value=processed_text, inline=False)
                    await processing_msg.edit(content=None, embed=embed)

                # パフォーマンス情報を追加
                total_time = time.time() - start_time
                embed.set_footer(
                    text=f"処理時間: {total_time:.2f}秒 "
                    f"(文字起こし: {transcription_time:.2f}s, AI処理: {ai_time:.2f}s)"
                )

                # Obsidianへの保存ボタンを追加
                view = TranscriptionView(
                    transcription=processed_text,
                    summary=ai_result["summary"],
                    obsidian_service=self.obsidian_service,
                    knowledge_manager=self.knowledge_manager,
                    message=message,
                )
                await message.reply(view=view)

            else:
                await processing_msg.edit(
                    content="❌ 音声の文字起こしに失敗しました。OpenAI APIキーが設定されているか確認してください。"
                )

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"音声処理エラー: {e}, 処理時間: {total_time:.2f}秒")

            error_msg = "❌ 音声処理中にエラーが発生しました"
            if "timeout" in str(e).lower():
                error_msg += "（タイムアウト）"
            elif "rate_limit" in str(e).lower():
                error_msg += "（API制限に達しました）"

            await message.reply(f"{error_msg}: {str(e)}")

        finally:
            # 一時ファイルを削除
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"一時ファイル削除: {temp_path}")
                except Exception as e:
                    logger.warning(f"一時ファイル削除失敗: {e}")


class TranscriptionView(discord.ui.View):
    """文字起こし結果のインタラクティブビュー"""

    def __init__(
        self,
        transcription: str,
        summary: str,
        obsidian_service: Optional[ObsidianGitHubService] = None,
        knowledge_manager: Optional["KnowledgeManager"] = None,
        message: Optional[discord.Message] = None,
    ):
        super().__init__(timeout=300)  # 5分でタイムアウト
        self.transcription = transcription
        self.summary = summary
        self.obsidian_service = obsidian_service
        self.knowledge_manager = knowledge_manager
        self.message = message

    @discord.ui.button(label="📝 Obsidianに保存", style=discord.ButtonStyle.primary)
    async def save_to_obsidian(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Obsidianに保存"""
        if not self.obsidian_service:
            await interaction.response.send_message("❌ Obsidian統合サービスが設定されていません。", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)

            # ファイル名を生成（タイムスタンプ + 要約の一部）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_summary = "".join(c for c in self.summary[:20] if c.isalnum() or c in "_ -")
            filename = f"voice_transcription_{timestamp}_{safe_summary}.md"

            # Obsidian形式のマークダウンを作成
            content = f"""# 音声文字起こし

## 要約
{self.summary}

## 全文
{self.transcription}

---
作成日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

            # Obsidianサービスを使って保存
            request_id = await self.obsidian_service.save_to_obsidian(
                filename=filename,
                content=content,
                directory="voice_transcriptions",
                metadata={
                    "type": "voice_transcription",
                    "created_at": datetime.now().isoformat(),
                    "discord_user": str(interaction.user),
                },
            )

            await interaction.followup.send(
                f"✅ Obsidianに保存しました！\n"
                f"📁 ファイル: `{filename}`\n"
                f"🆔 リクエストID: `{request_id}`\n"
                f"📊 処理状況は `/obsidian status {request_id}` で確認できます。",
                ephemeral=True,
            )

        except Exception as e:
            logging.getLogger(__name__).error(f"Obsidian保存エラー: {e}")
            await interaction.followup.send(f"❌ 保存中にエラーが発生しました: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🐦 Xに投稿", style=discord.ButtonStyle.secondary)
    async def post_to_twitter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """X（Twitter）に投稿（実装予定）"""
        await interaction.response.send_message(
            f"以下の内容でXに投稿する機能は開発中です:\n\n{self.summary[:100]}...", ephemeral=True
        )

    @discord.ui.button(label="🔄 再生成", style=discord.ButtonStyle.secondary)
    async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        """AIによる再生成"""
        await interaction.response.send_message("再生成機能は現在開発中です。", ephemeral=True)

    @discord.ui.button(label="🧠 PKMに保存", style=discord.ButtonStyle.success)
    async def save_to_pkm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save voice transcription to PKM system with auto-tagging."""
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
            title = self.summary[:50].strip() if self.summary else "Discord voice note"
            if len(title) < len(self.summary):
                title += "..."

            try:
                # Auto-suggest tags using KnowledgeManager
                tag_suggestions = await self.knowledge_manager.suggest_tags_for_content(
                    content=self.transcription, title=title, max_suggestions=5
                )

                # Extract high-confidence tags (>0.8)
                auto_tags = [
                    suggestion["tag"]
                    for suggestion in tag_suggestions
                    if suggestion["confidence"] > 0.8
                ]

                # Ensure we have at least basic tags
                if not auto_tags:
                    auto_tags = ["fleeting-note", "voice"]
                elif "fleeting-note" not in auto_tags:
                    auto_tags.append("fleeting-note")
                if "voice" not in auto_tags:
                    auto_tags.append("voice")

                logger.info(f"Auto-generated tags for voice PKM: {auto_tags}")

                # Create note in PKM system
                note_id = await self.knowledge_manager.create_note(
                    title=title,
                    content=self.transcription,
                    tags=auto_tags,
                    source_type="voice",
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
                    "🧠 **音声PKMノートを作成しました！**",
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

                logger.info(f"Voice PKM note created successfully: {note_id}")

            except Exception as e:
                logger.error(f"Error creating voice PKM note: {e}")
                await interaction.followup.send(
                    f"❌ 音声PKMノートの作成中にエラーが発生しました: {str(e)}\n" f"💡 管理者にお問い合わせください。",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in voice save_to_pkm button: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ エラーが発生しました。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ エラーが発生しました。", ephemeral=True)
            except Exception:
                logger.error("Failed to send error message to user")

    @discord.ui.button(label="🔗 関連ノート", style=discord.ButtonStyle.secondary)
    async def show_related_notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show related notes based on voice transcription content."""
        logger = logging.getLogger(__name__)

        try:
            if not self.knowledge_manager:
                await interaction.response.send_message("❌ PKMサービスが利用できません。", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            # Search for related notes using transcription and summary
            search_query = (
                f"{self.summary} {self.transcription[:200]}"  # Limit to avoid token limit
            )

            try:
                related_notes = await self.knowledge_manager.search_notes(
                    query=search_query, limit=5
                )

                if not related_notes:
                    await interaction.followup.send("🔍 関連するノートが見つかりませんでした。", ephemeral=True)
                    return

                # Build response with related notes
                response_parts = [f"🔗 **音声関連ノート ({len(related_notes)}件)**\n"]

                for i, note in enumerate(related_notes, 1):
                    note_title = note.get("title", "無題")[:40]
                    note_tags = note.get("tags", [])
                    created_at = note.get("created_at", "")
                    source_type = note.get("source_type", "")

                    # Format creation date
                    date_str = ""
                    if created_at:
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            date_str = f" ({dt.strftime('%m-%d')})"
                        except Exception:
                            pass

                    # Add source type indicator
                    source_emoji = (
                        "🎤" if source_type == "voice" else "💬" if source_type == "discord" else "📝"
                    )

                    # Show tags if available
                    tag_str = ""
                    if note_tags and isinstance(note_tags, list):
                        tag_str = f" `{', '.join(note_tags[:3])}`"

                    response_parts.append(
                        f"{i}. {source_emoji} **{note_title}**{date_str}{tag_str}"
                    )

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
            logger.error(f"Error in voice show_related_notes: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ エラーが発生しました。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ エラーが発生しました。", ephemeral=True)
            except Exception:
                logger.error("Failed to send error message to user")


async def setup(bot):
    """Cogをセットアップ"""
    obsidian_service = getattr(bot, "obsidian_service", None)
    note_processing_service = getattr(bot, "note_processing_service", None)
    knowledge_manager = getattr(bot, "knowledge_manager", None)
    await bot.add_cog(Voice(bot, obsidian_service, note_processing_service, knowledge_manager))
