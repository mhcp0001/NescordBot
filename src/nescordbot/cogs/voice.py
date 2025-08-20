import asyncio
import io
import os
from datetime import datetime
from typing import Optional

import discord
import openai
from discord import app_commands
from discord.ext import commands

from ..services import ObsidianGitHubService


class Voice(commands.Cog):
    """音声処理関連のコマンドを管理するCog"""

    def __init__(self, bot, obsidian_service: Optional[ObsidianGitHubService] = None):
        self.bot = bot
        self.openai_client = None
        self.obsidian_service = obsidian_service
        self.setup_openai()

    def setup_openai(self):
        """OpenAI APIの設定"""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            openai.api_key = api_key
            self.openai_client = openai
        else:
            import logging

            logging.getLogger(__name__).warning("OpenAI APIキーが設定されていません")

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """音声ファイルを文字起こし"""
        if not self.openai_client:
            return None

        try:
            # OpenAI Whisper APIを使用
            with open(audio_path, "rb") as audio_file:
                transcript = await asyncio.to_thread(
                    self.openai_client.Audio.transcribe,
                    model="whisper-1",
                    file=audio_file,
                    language="ja",
                )

            return str(transcript.text) if transcript.text else None

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"音声認識エラー: {e}")
            return None

    async def process_with_ai(self, text: str) -> dict:
        """AIで文字起こし結果を処理"""
        if not self.openai_client:
            return {"processed": text, "summary": "AI処理は利用できません"}

        try:
            # GPTで整形
            response = await asyncio.to_thread(
                self.openai_client.ChatCompletion.create,
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは文字起こしされたテキストを整形し、要約するアシスタントです。誤字脱字を修正し、読みやすく整形してください。",
                    },
                    {"role": "user", "content": f"以下のテキストを整形し、短い要約も作成してください:\n\n{text}"},
                ],
                temperature=0.3,
            )

            processed_text = response.choices[0].message.content

            # 要約を生成
            summary_response = await asyncio.to_thread(
                self.openai_client.ChatCompletion.create,
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "1行で要約してください。"},
                    {"role": "user", "content": processed_text},
                ],
                temperature=0.3,
                max_tokens=100,
            )

            summary = summary_response.choices[0].message.content

            return {"processed": processed_text, "summary": summary}

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"AI処理エラー: {e}")
            return {"processed": text, "summary": "AI処理中にエラーが発生しました"}

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
        try:
            # 処理中の表示
            processing_msg = await message.reply("🎤 音声を処理しています...")

            # 音声ファイルをダウンロード
            audio_data = await attachment.read()
            temp_path = os.path.join("data", f"temp_{message.id}.ogg")
            os.makedirs("data", exist_ok=True)

            with open(temp_path, "wb") as f:
                f.write(audio_data)

            # 文字起こし
            transcription = await self.transcribe_audio(temp_path)

            if transcription:
                # AI処理
                ai_result = await self.process_with_ai(transcription)

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

                # Obsidianへの保存ボタンを追加
                view = TranscriptionView(
                    transcription=processed_text,
                    summary=ai_result["summary"],
                    obsidian_service=self.obsidian_service,
                )
                await message.reply(view=view)

            else:
                await processing_msg.edit(
                    content="❌ 音声の文字起こしに失敗しました。OpenAI APIキーが設定されているか確認してください。"
                )

            # 一時ファイルを削除
            if os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"音声処理エラー: {e}")
            await message.reply(f"❌ エラーが発生しました: {str(e)}")


class TranscriptionView(discord.ui.View):
    """文字起こし結果のインタラクティブビュー"""

    def __init__(
        self,
        transcription: str,
        summary: str,
        obsidian_service: Optional[ObsidianGitHubService] = None,
    ):
        super().__init__(timeout=300)  # 5分でタイムアウト
        self.transcription = transcription
        self.summary = summary
        self.obsidian_service = obsidian_service

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
            import logging

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


async def setup(bot):
    """Cogをセットアップ"""
    await bot.add_cog(Voice(bot))
