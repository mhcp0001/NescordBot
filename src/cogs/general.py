"""
General commands cog for NescordBot.

This module contains basic Discord commands like help, status, and ping.
"""

import platform
from datetime import datetime, timezone

import discord
import psutil
from discord import app_commands
from discord.ext import commands

try:
    from src.logger import get_logger
except ImportError:
    # Fallback for Railway deployment
    import sys
    from pathlib import Path

    parent_path = str(Path(__file__).parent.parent.parent)
    if parent_path not in sys.path:
        sys.path.insert(0, parent_path)

    try:
        from src.logger import get_logger
    except ImportError:
        from logger import get_logger  # type: ignore


class General(commands.Cog):
    """
    General commands cog providing basic bot functionality.

    Includes help, status, and ping commands with proper error handling
    and logging integration.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialize the General cog.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = get_logger("cogs.general")
        self.logger.info("General cog initialized")

    @app_commands.command(name="help", description="Botの使い方とコマンド一覧を表示します")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """
        Display help information and available commands.

        Args:
            interaction: The Discord interaction
        """
        try:
            embed = discord.Embed(
                title="📖 NescordBot ヘルプ",
                description="音声認識とAI機能を備えたDiscord Bot",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )

            # Main features
            embed.add_field(
                name="🎤 音声メッセージ機能",
                value=(
                    "音声メッセージやファイルを送信すると、自動的に文字起こしされます。\n"
                    "対応形式: ogg, mp3, wav, m4a, webm\n"
                    "最大サイズ: 25MB（設定により変更可能）"
                ),
                inline=False,
            )

            # Commands
            embed.add_field(
                name="📝 利用可能なコマンド",
                value=(
                    "`/help` - このヘルプを表示\n"
                    "`/status` - Botのステータス情報を表示\n"
                    "`/ping` - Botの応答速度を測定\n"
                    "\n*今後追加予定: 検索、Obsidian連携、X投稿など*"
                ),
                inline=False,
            )

            # Tips and usage
            embed.add_field(
                name="💡 使い方のコツ",
                value=(
                    "• 日本語での音声認識に最適化されています\n"
                    "• 音声は明瞭に話すとより良い結果が得られます\n"
                    "• 文字起こし後、AIが内容を自動で整形します\n"
                    "• 処理中は ⏳ リアクションが表示されます"
                ),
                inline=False,
            )

            # Footer with version info
            embed.set_footer(
                text=f"discord.py v{discord.__version__} | Made with ❤️",
                icon_url=self.bot.user.avatar.url
                if self.bot.user and self.bot.user.avatar
                else None,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.logger.info(f"Help command used by {interaction.user} in {interaction.guild}")

        except Exception as e:
            self.logger.error(f"Error in help command: {e}")
            await self._send_error_response(interaction, "ヘルプ情報の取得中にエラーが発生しました。")

    @app_commands.command(name="status", description="Botの動作状況とシステム情報を表示します")
    async def status_command(self, interaction: discord.Interaction) -> None:
        """
        Display bot status and system information.

        Args:
            interaction: The Discord interaction
        """
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            # Get disk usage (handle different platforms)
            try:
                if platform.system() == "Windows":
                    disk = psutil.disk_usage("C:")
                else:
                    disk = psutil.disk_usage("/")
            except Exception:
                disk = None

            # Bot metrics
            latency_ms = round(self.bot.latency * 1000)
            guild_count = len(self.bot.guilds)

            # Calculate total user count safely
            user_count = 0
            for guild in self.bot.guilds:
                if guild.member_count:
                    user_count += guild.member_count

            # Create status embed
            embed = discord.Embed(
                title="📊 Bot ステータス",
                color=self._get_status_color(latency_ms, cpu_percent, memory.percent),
                timestamp=datetime.now(timezone.utc),
            )

            # Bot information
            embed.add_field(
                name="🤖 Bot情報",
                value=(
                    f"**レイテンシ:** {latency_ms}ms\n"
                    f"**接続サーバー数:** {guild_count:,}\n"
                    f"**総ユーザー数:** {user_count:,}"
                ),
                inline=True,
            )

            # System information
            system_info = f"**CPU使用率:** {cpu_percent:.1f}%\n" f"**メモリ使用率:** {memory.percent:.1f}%\n"
            if disk:
                system_info += f"**ディスク使用率:** {disk.percent:.1f}%"
            else:
                system_info += "**ディスク使用率:** 取得不可"

            embed.add_field(name="💻 システム情報", value=system_info, inline=True)

            # Environment information
            embed.add_field(
                name="🐍 環境情報",
                value=(
                    f"**Python:** {platform.python_version()}\n"
                    f"**discord.py:** {discord.__version__}\n"
                    f"**OS:** {platform.system()} {platform.release()}"
                ),
                inline=True,
            )

            # Add status indicator
            status_text = self._get_status_text(latency_ms, cpu_percent, memory.percent)
            embed.add_field(name="🔄 動作状況", value=status_text, inline=False)

            await interaction.response.send_message(embed=embed)
            self.logger.info(f"Status command used by {interaction.user} in {interaction.guild}")

        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            await self._send_error_response(interaction, "ステータス情報の取得中にエラーが発生しました。")

    @app_commands.command(name="ping", description="Botの応答速度を測定します")
    async def ping_command(self, interaction: discord.Interaction) -> None:
        """
        Measure and display bot latency.

        Args:
            interaction: The Discord interaction
        """
        try:
            # Calculate WebSocket latency
            ws_latency = round(self.bot.latency * 1000)

            # Measure response time
            start_time = datetime.now()
            await interaction.response.defer()
            response_time = round((datetime.now() - start_time).total_seconds() * 1000)

            # Create ping embed
            embed = discord.Embed(
                title="🏓 Pong!",
                color=self._get_ping_color(ws_latency),
                timestamp=datetime.now(timezone.utc),
            )

            embed.add_field(name="📡 WebSocket レイテンシ", value=f"**{ws_latency}ms**", inline=True)

            embed.add_field(name="⚡ API応答時間", value=f"**{response_time}ms**", inline=True)

            # Add performance rating
            rating = self._get_performance_rating(ws_latency)
            embed.add_field(name="📈 パフォーマンス", value=rating, inline=False)

            await interaction.followup.send(embed=embed)
            self.logger.info(
                f"Ping command used by {interaction.user} in {interaction.guild} "
                f"(WS: {ws_latency}ms, API: {response_time}ms)"
            )

        except Exception as e:
            self.logger.error(f"Error in ping command: {e}")
            await self._send_error_response(interaction, "応答速度の測定中にエラーが発生しました。")

    def _get_status_color(self, latency: int, cpu: float, memory: float) -> discord.Color:
        """Get status color based on system metrics."""
        if latency > 200 or cpu > 80 or memory > 80:
            return discord.Color.red()
        elif latency > 100 or cpu > 60 or memory > 60:
            return discord.Color.yellow()
        else:
            return discord.Color.green()

    def _get_ping_color(self, latency: int) -> discord.Color:
        """Get ping color based on latency."""
        if latency < 50:
            return discord.Color.green()
        elif latency < 100:
            return discord.Color.yellow()
        elif latency < 200:
            return discord.Color.orange()
        else:
            return discord.Color.red()

    def _get_status_text(self, latency: int, cpu: float, memory: float) -> str:
        """Get status text based on metrics."""
        if latency > 200 or cpu > 80 or memory > 80:
            return "🔴 **重い負荷** - パフォーマンスが低下しています"
        elif latency > 100 or cpu > 60 or memory > 60:
            return "🟡 **中程度の負荷** - 通常より少し遅い可能性があります"
        else:
            return "🟢 **正常** - すべて順調に動作しています"

    def _get_performance_rating(self, latency: int) -> str:
        """Get performance rating based on latency."""
        if latency < 50:
            return "🟢 **優秀** - 非常に高速です"
        elif latency < 100:
            return "🟡 **良好** - 通常の応答速度です"
        elif latency < 200:
            return "🟠 **普通** - 少し遅めですが問題ありません"
        else:
            return "🔴 **遅延** - ネットワークに問題がある可能性があります"

    async def _send_error_response(self, interaction: discord.Interaction, message: str) -> None:
        """Send error response to user."""
        embed = discord.Embed(title="❌ エラー", description=message, color=discord.Color.red())

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Failed to send error response: {e}")

    @commands.Cog.listener()
    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """
        Handle application command errors.

        Args:
            interaction: The Discord interaction
            error: The error that occurred
        """
        self.logger.error(
            f"App command error in {interaction.command}: {error} "
            f"(User: {interaction.user}, Guild: {interaction.guild})"
        )

        if isinstance(error, app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ クールダウン中",
                description=f"このコマンドは {error.retry_after:.1f} 秒後に再実行できます。",
                color=discord.Color.orange(),
            )
        elif isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="🚫 権限不足", description="このコマンドを実行する権限がありません。", color=discord.Color.red()
            )
        elif isinstance(error, app_commands.BotMissingPermissions):
            embed = discord.Embed(
                title="🤖 Bot権限不足", description="Botにこの操作を実行する権限がありません。", color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❌ エラー", description="コマンドの実行中に予期しないエラーが発生しました。", color=discord.Color.red()
            )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as send_error:
            self.logger.error(f"Failed to send error message: {send_error}")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the General cog to the bot.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(General(bot))
