"""
Admin commands for NescordBot.

Provides administrative commands for log viewing, configuration management,
and database operations.
"""

import logging
from datetime import datetime
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
                    title="❌ 操作がキャンセルされました", color=discord.Color.greyple(), timestamp=datetime.now()
                )

                await interaction.edit_original_response(embed=embed, view=None)

        except Exception as e:
            self.logger.error(f"Error in cleardb command: {e}")
            await interaction.followup.send("❌ データベースクリア中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="debug", description="システム設定と状態の診断")
    @app_commands.describe(category="診断カテゴリ (config, services, queue, github, process)")
    async def debug(self, interaction: discord.Interaction, category: str = "config"):
        """Debug system configuration and services."""
        await interaction.response.defer(ephemeral=True)

        try:
            if category.lower() == "config":
                await self._debug_config(interaction)
            elif category.lower() == "services":
                await self._debug_services(interaction)
            elif category.lower() == "queue":
                await self._debug_queue(interaction)
            elif category.lower() == "github":
                await self._debug_github(interaction)
            elif category.lower() == "process":
                await self._debug_process(interaction)
            else:
                await interaction.followup.send(
                    "❌ 無効なカテゴリです。利用可能: `config`, `services`, `queue`, `github`, `process`",
                    ephemeral=True,
                )

        except Exception as e:
            self.logger.error(f"Error in debug command: {e}")
            await interaction.followup.send("❌ デバッグ中にエラーが発生しました。", ephemeral=True)

    async def _debug_config(self, interaction: discord.Interaction):
        """Debug configuration settings."""
        embed = discord.Embed(
            title="🔧 設定診断レポート", color=discord.Color.blue(), timestamp=datetime.now()
        )

        # Check ObsidianGitHub configuration
        config = self.bot.config
        obsidian_enabled = getattr(config, "github_obsidian_enabled", False)

        # Basic config status
        embed.add_field(
            name="📝 Obsidian GitHub統合", value="✅ 有効" if obsidian_enabled else "❌ 無効", inline=True
        )

        # Check required environment variables
        required_vars = [
            ("GITHUB_TOKEN", getattr(config, "github_token", None)),
            ("GITHUB_REPO_OWNER", getattr(config, "github_repo_owner", None)),
            ("GITHUB_REPO_NAME", getattr(config, "github_repo_name", None)),
        ]

        missing_vars = []
        config_status = []

        for var_name, var_value in required_vars:
            if var_value:
                config_status.append(f"✅ {var_name}")
            else:
                config_status.append(f"❌ {var_name}")
                missing_vars.append(var_name)

        embed.add_field(name="🔑 必須環境変数", value="\n".join(config_status) or "なし", inline=True)

        # Service initialization status
        service_status = (
            "✅ 初期化済み"
            if hasattr(self.bot, "obsidian_service") and self.bot.obsidian_service
            else "❌ 未初期化"
        )
        embed.add_field(name="🔧 サービス状態", value=service_status, inline=True)

        # Recommendations
        if missing_vars or not obsidian_enabled:
            recommendations = []
            if not obsidian_enabled:
                recommendations.append("• `GITHUB_OBSIDIAN_ENABLED=true` を設定")
            if missing_vars:
                recommendations.append(f"• 不足環境変数を設定: {', '.join(missing_vars)}")

            embed.add_field(name="💡 推奨アクション", value="\n".join(recommendations), inline=False)

        embed.set_footer(text="本番環境では管理者にお問い合わせください")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _debug_services(self, interaction: discord.Interaction):
        """Debug services status."""
        embed = discord.Embed(
            title="🔧 サービス診断レポート", color=discord.Color.blue(), timestamp=datetime.now()
        )

        # Check services availability
        services_info = [
            (
                "DatabaseService",
                hasattr(self.bot, "database_service") and self.bot.database_service,
            ),
            (
                "ObsidianService",
                hasattr(self.bot, "obsidian_service") and self.bot.obsidian_service,
            ),
            (
                "GitHubAuthManager",
                hasattr(self.bot, "github_auth_manager") and self.bot.github_auth_manager,
            ),
            (
                "SecurityValidator",
                hasattr(self.bot, "security_validator") and self.bot.security_validator,
            ),
        ]

        services_status = []
        for service_name, is_available in services_info:
            status = "✅ 利用可能" if is_available else "❌ 未初期化"
            services_status.append(f"{service_name}: {status}")

        embed.add_field(name="🔧 サービス状態", value="\n".join(services_status), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _debug_queue(self, interaction: discord.Interaction):
        """Debug queue status and processing statistics."""
        try:
            obsidian_service = getattr(self.bot, "obsidian_service", None)

            if not obsidian_service:
                await interaction.followup.send(
                    "❌ ObsidianGitHubService not available", ephemeral=True
                )
                return

            # Get processing statistics
            stats = await obsidian_service.get_processing_statistics()

            if stats.get("error"):
                await interaction.followup.send(f"❌ Queue診断エラー: {stats['error']}", ephemeral=True)
                return

            # Format queue status
            batch_stats = stats.get("batch_processor", {})
            status_counts = stats.get("status_counts", {})

            embed = discord.Embed(
                title="📊 キュー状態診断",
                color=0x00FF00 if batch_stats.get("initialized", False) else 0xFF0000,
                timestamp=datetime.now(),
            )

            # Processing Status
            processing_active = batch_stats.get("processing_active", False)
            embed.add_field(
                name="⚙️ 処理状態", value=f"{'🟢 動作中' if processing_active else '🔴 停止中'}", inline=True
            )

            # Queue Status
            queue_status = batch_stats.get("queue_status", {})
            queue_text = ""
            for status, count in queue_status.items():
                emoji = {"pending": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌"}.get(
                    status, "📋"
                )
                queue_text += f"{emoji} {status}: {count}\n"

            embed.add_field(
                name="📈 キュー統計", value=queue_text if queue_text else "データなし", inline=True
            )

            # Request Status
            request_text = ""
            for status, count in status_counts.items():
                emoji = {"queued": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌"}.get(
                    status, "📋"
                )
                request_text += f"{emoji} {status}: {count}\n"

            embed.add_field(
                name="🔍 リクエスト状況", value=request_text if request_text else "データなし", inline=True
            )

            # Recent requests
            recent_requests = await obsidian_service.list_recent_requests(5)
            if recent_requests:
                recent_text = ""
                for req in recent_requests[:5]:
                    status_emoji = {
                        "queued": "⏳",
                        "processing": "🔄",
                        "completed": "✅",
                        "failed": "❌",
                    }.get(req.status, "📋")
                    recent_text += f"{status_emoji} {req.file_path} ({req.status})\n"
                embed.add_field(name="📝 最近のリクエスト", value=recent_text, inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"Debug queue command error: {e}", exc_info=True)
            await interaction.followup.send(f"❌ キュー診断エラー: {str(e)}", ephemeral=True)

    async def _debug_github(self, interaction: discord.Interaction):
        """Debug GitHub connection and repository access."""
        try:
            obsidian_service = getattr(self.bot, "obsidian_service", None)

            if not obsidian_service:
                await interaction.followup.send(
                    "❌ ObsidianGitHubService not available", ephemeral=True
                )
                return

            # Get batch processor
            batch_processor = getattr(obsidian_service, "batch_processor", None)
            if not batch_processor:
                await interaction.followup.send("❌ BatchProcessor not available", ephemeral=True)
                return

            # Get Git operations service
            git_service = getattr(batch_processor, "git_operations", None)
            if not git_service:
                await interaction.followup.send(
                    "❌ GitOperationService not available", ephemeral=True
                )
                return

            embed = discord.Embed(title="🔗 GitHub接続診断", color=0x00FF00, timestamp=datetime.now())

            # Test repository status
            try:
                repo_status = await git_service.get_repository_status()

                embed.add_field(
                    name="📂 リポジトリ状態",
                    value=f"✅ 接続成功\n🏷️ ブランチ: {repo_status.get('branch', 'unknown')}",
                    inline=True,
                )

            except Exception as repo_error:
                embed.add_field(name="📂 リポジトリ状態", value=f"❌ 接続失敗: {str(repo_error)}", inline=True)
                embed.colour = 0xFF0000

            # Test authentication
            auth_manager = getattr(batch_processor, "auth_manager", None)
            if auth_manager:
                try:
                    # Simple auth check (this method should exist)
                    auth_status = getattr(auth_manager, "_initialized", False)
                    embed.add_field(
                        name="🔐 認証状態", value="✅ 認証済み" if auth_status else "❌ 未認証", inline=True
                    )
                except Exception as auth_error:
                    embed.add_field(name="🔐 認証状態", value=f"❌ 認証エラー: {str(auth_error)}", inline=True)
                    embed.colour = 0xFF0000

            # Configuration check
            config = self.bot.config
            github_enabled = getattr(config, "github_obsidian_enabled", False)
            repo_owner = getattr(config, "github_repo_owner", None)
            repo_name = getattr(config, "github_repo_name", None)

            config_text = f"🔧 有効: {'✅' if github_enabled else '❌'}\n"
            config_text += f"👤 オーナー: {repo_owner or '❌ 未設定'}\n"
            config_text += f"📁 リポジトリ: {repo_name or '❌ 未設定'}"

            embed.add_field(name="⚙️ GitHub設定", value=config_text, inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"Debug GitHub command error: {e}", exc_info=True)
            await interaction.followup.send(f"❌ GitHub診断エラー: {str(e)}", ephemeral=True)

    async def _debug_process(self, interaction: discord.Interaction):
        """Manually trigger batch processing for testing."""
        try:
            obsidian_service = getattr(self.bot, "obsidian_service", None)

            if not obsidian_service:
                await interaction.followup.send(
                    "❌ ObsidianGitHubService not available", ephemeral=True
                )
                return

            batch_processor = getattr(obsidian_service, "batch_processor", None)
            if not batch_processor:
                await interaction.followup.send("❌ BatchProcessor not available", ephemeral=True)
                return

            # Trigger manual batch processing
            result = await batch_processor.process_batch_manually()

            if result.get("success"):
                files_processed = result.get("files_processed", 0)
                remaining = result.get("remaining_pending", 0)

                embed = discord.Embed(title="🔄 手動バッチ処理完了", color=0x00FF00, timestamp=datetime.now())

                embed.add_field(
                    name="📊 処理結果",
                    value=f"✅ 処理済み: {files_processed}\n⏳ 残り: {remaining}",
                    inline=True,
                )

                if result.get("completed", 0) > 0:
                    embed.add_field(name="✅ 成功", value=str(result.get("completed", 0)), inline=True)

                if result.get("failed", 0) > 0:
                    embed.add_field(name="❌ 失敗", value=str(result.get("failed", 0)), inline=True)
                    embed.colour = 0xFFA500  # Orange for partial success

            else:
                embed = discord.Embed(title="❌ 手動バッチ処理失敗", color=0xFF0000, timestamp=datetime.now())
                embed.add_field(name="エラー詳細", value=result.get("error", "不明なエラー"), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"Debug process command error: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 手動処理エラー: {str(e)}", ephemeral=True)

    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions."""
        # Check if user is bot owner
        app_info = await self.bot.application_info()
        if interaction.user.id == app_info.owner.id:
            return True

        # Check if user has administrator permissions
        if interaction.guild and isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                return True

            # Check custom admin roles (stored in database)
            try:
                admin_roles = await self.bot.database_service.get_json("admin_roles")
                if admin_roles:
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
            if hasattr(item, "disabled"):
                item.disabled = True


async def setup(bot):
    """Set up the AdminCog."""
    await bot.add_cog(AdminCog(bot))
