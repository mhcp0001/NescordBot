"""
Admin commands for NescordBot.

Provides administrative commands for log viewing, configuration management,
and database operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """
    Administrative commands for bot management.

    Provides commands for viewing logs, managing configuration,
    and monitoring database statistics.
    """

    def __init__(self, bot):
        """Initialize the AdminCog."""
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @app_commands.command(name="logs", description="最新のログを表示します")
    @app_commands.describe(level="ログレベル (DEBUG, INFO, WARNING, ERROR)", lines="表示する行数 (デフォルト: 10)")
    async def logs(
        self,
        interaction: discord.Interaction,
        level: Optional[str] = None,
        lines: Optional[int] = 10,
    ):
        """Display recent logs."""
        await interaction.response.defer()

        try:
            # Read logs from file
            log_file_path = self.bot.data_dir.parent / "logs" / "bot.log"

            if not log_file_path.exists():
                await interaction.followup.send("❌ ログファイルが見つかりません。")
                return

            # Read last N lines
            with open(log_file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

            # Filter by level if specified
            if level:
                level_upper = level.upper()
                filtered_lines = [line for line in all_lines if level_upper in line]
            else:
                filtered_lines = all_lines

            # Get last N lines
            recent_lines = filtered_lines[-lines:] if lines else filtered_lines[-10:]

            if not recent_lines:
                await interaction.followup.send("📋 指定された条件に一致するログがありません。")
                return

            # Format logs for Discord
            log_content = "".join(recent_lines)

            # Split into chunks if too long for Discord
            if len(log_content) > 1900:  # Leave room for code block formatting
                log_content = log_content[-1900:]
                log_content = "...\n" + log_content

            embed = discord.Embed(
                title=f"📋 最新のログ ({len(recent_lines)}行)",
                description=f"```\n{log_content}\n```",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            if level:
                embed.add_field(name="フィルター", value=f"レベル: {level.upper()}", inline=True)

            embed.set_footer(text="NescordBot ログビューア")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in logs command: {e}")
            await interaction.followup.send("❌ ログの取得中にエラーが発生しました。")

    @app_commands.command(name="dbstats", description="データベースの統計情報を表示します")
    async def dbstats(self, interaction: discord.Interaction):
        """Display database statistics."""
        await interaction.response.defer()

        try:
            if not self.bot.database_service.is_initialized:
                await interaction.followup.send("❌ データベースが初期化されていません。")
                return

            # Get database statistics
            stats = await self.bot.database_service.get_stats()

            embed = discord.Embed(
                title="📊 データベース統計", color=discord.Color.green(), timestamp=datetime.now()
            )

            embed.add_field(name="総キー数", value=f"{stats['total_keys']:,}", inline=True)

            embed.add_field(name="データベースパス", value=f"`{stats['db_path']}`", inline=False)

            if not stats["is_memory"]:
                size_mb = stats["db_size_bytes"] / (1024 * 1024)
                embed.add_field(name="ファイルサイズ", value=f"{size_mb:.2f} MB", inline=True)
            else:
                embed.add_field(name="タイプ", value="メモリ内データベース", inline=True)

            embed.add_field(
                name="初期化状態", value="✅ 初期化済み" if stats["is_initialized"] else "❌ 未初期化", inline=True
            )

            embed.set_footer(text="NescordBot データベース管理")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in dbstats command: {e}")
            await interaction.followup.send("❌ データベース統計の取得中にエラーが発生しました。")

    @app_commands.command(name="config", description="ボット設定を表示します")
    async def config(self, interaction: discord.Interaction):
        """Display current bot configuration."""
        await interaction.response.defer()

        try:
            config = self.bot.config

            embed = discord.Embed(
                title="⚙️ ボット設定", color=discord.Color.orange(), timestamp=datetime.now()
            )

            # Add safe configuration fields (excluding sensitive data)
            if hasattr(config, "max_audio_size_mb"):
                embed.add_field(
                    name="最大音声ファイルサイズ", value=f"{config.max_audio_size_mb} MB", inline=True
                )

            if hasattr(config, "speech_language"):
                embed.add_field(name="音声言語", value=config.speech_language, inline=True)

            if hasattr(config, "log_level"):
                embed.add_field(name="ログレベル", value=config.log_level, inline=True)

            # Add bot information
            embed.add_field(
                name="Bot ID", value=f"`{self.bot.user.id}`" if self.bot.user else "不明", inline=True
            )

            embed.add_field(name="Guild数", value=f"{len(self.bot.guilds)}", inline=True)

            embed.add_field(
                name="起動時間",
                value=f"<t:{int(self.bot.uptime.timestamp())}:R>"
                if hasattr(self.bot, "uptime")
                else "不明",
                inline=True,
            )

            embed.set_footer(text="NescordBot 設定管理")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in config command: {e}")
            await interaction.followup.send("❌ 設定の取得中にエラーが発生しました。")

    @app_commands.command(name="setconfig", description="設定を更新します")
    @app_commands.describe(key="設定キー", value="設定値")
    async def setconfig(self, interaction: discord.Interaction, key: str, value: str):
        """Update a configuration setting."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Check permissions (only bot owner or specific roles)
            if not await self._check_admin_permissions(interaction):
                await interaction.followup.send("❌ この操作を実行する権限がありません。", ephemeral=True)
                return

            # Store configuration in database
            config_key = f"config:{key}"
            await self.bot.database_service.set(config_key, value)

            # Log the configuration change
            self.logger.info(f"Configuration updated by {interaction.user}: {key} = {value}")

            embed = discord.Embed(
                title="✅ 設定が更新されました", color=discord.Color.green(), timestamp=datetime.now()
            )

            embed.add_field(name="キー", value=f"`{key}`", inline=True)
            embed.add_field(name="値", value=f"`{value}`", inline=True)

            embed.set_footer(text="設定は次回起動時に反映されます")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"Error in setconfig command: {e}")
            await interaction.followup.send("❌ 設定の更新中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="cleardb", description="データベースをクリアします（危険）")
    async def cleardb(self, interaction: discord.Interaction):
        """Clear all database data (dangerous operation)."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Check permissions
            if not await self._check_admin_permissions(interaction):
                await interaction.followup.send("❌ この操作を実行する権限がありません。", ephemeral=True)
                return

            # Confirmation view
            view = ConfirmationView()

            embed = discord.Embed(
                title="⚠️ データベースクリア確認",
                description="この操作により、すべてのデータが削除されます。\n**この操作は取り消せません。**",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            # Wait for confirmation
            await view.wait()

            if view.confirmed:
                # Get stats before clearing
                stats = await self.bot.database_service.get_stats()
                keys_count = stats["total_keys"]

                # Clear database
                await self.bot.database_service.clear()

                # Log the action
                self.logger.warning(
                    f"Database cleared by {interaction.user}: {keys_count} keys deleted"
                )

                embed = discord.Embed(
                    title="✅ データベースがクリアされました",
                    description=f"{keys_count} 個のキーが削除されました。",
                    color=discord.Color.green(),
                    timestamp=datetime.now(),
                )

                await interaction.edit_original_response(embed=embed, view=None)
            else:
                embed = discord.Embed(
                    title="❌ 操作がキャンセルされました", color=discord.Color.grey(), timestamp=datetime.now()
                )

                await interaction.edit_original_response(embed=embed, view=None)

        except Exception as e:
            self.logger.error(f"Error in cleardb command: {e}")
            await interaction.followup.send("❌ データベースクリア中にエラーが発生しました。", ephemeral=True)

    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions."""
        # Check if user is bot owner
        app_info = await self.bot.application_info()
        if interaction.user.id == app_info.owner.id:
            return True

        # Check if user has administrator permissions
        if interaction.guild and interaction.user.guild_permissions.administrator:
            return True

        # Check custom admin roles (stored in database)
        try:
            admin_roles = await self.bot.database_service.get_json("admin_roles")
            if admin_roles and interaction.guild:
                user_role_ids = [role.id for role in interaction.user.roles]
                if any(role_id in admin_roles for role_id in user_role_ids):
                    return True
        except Exception:
            pass  # Ignore database errors for permission checks

        return False


class ConfirmationView(discord.ui.View):
    """Confirmation dialog for dangerous operations."""

    def __init__(self):
        super().__init__(timeout=30.0)
        self.confirmed = False

    @discord.ui.button(label="確認", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the dangerous operation."""
        self.confirmed = True
        button.disabled = True
        self.cancel_button.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the operation."""
        self.confirmed = False
        button.disabled = True
        self.confirm.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        """Handle timeout."""
        self.confirmed = False
        for item in self.children:
            item.disabled = True


async def setup(bot):
    """Set up the AdminCog."""
    await bot.add_cog(AdminCog(bot))
