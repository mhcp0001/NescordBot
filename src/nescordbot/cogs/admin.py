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
    @app_commands.describe(category="診断カテゴリ (config, services, queue, github, process, openai)")
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
            elif category.lower() == "openai":
                await self._debug_openai(interaction)
            else:
                await interaction.followup.send(
                    "❌ 無効なカテゴリです。利用可能: `config`, `services`, `queue`, `github`, "
                    "`process`, `openai`",
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

    async def _debug_openai(self, interaction: discord.Interaction):
        """OpenAI API診断"""
        try:
            # Get NoteProcessingService from bot
            note_service = getattr(self.bot, "note_processing_service", None)

            if not note_service:
                embed = discord.Embed(
                    title="🤖 OpenAI API診断",
                    description="❌ NoteProcessingServiceが初期化されていません",
                    colour=discord.Colour.red(),
                )
                await interaction.followup.send(embed=embed)
                return

            # Check API status
            status = await note_service.check_api_status()

            # Create embed based on status
            if status.get("available"):
                embed = discord.Embed(title="🤖 OpenAI API診断", colour=discord.Colour.green())
                embed.add_field(name="🔐 API状態", value="✅ 利用可能", inline=True)
                embed.add_field(name="🤖 モデル", value=status.get("model", "unknown"), inline=True)
                embed.add_field(name="📊 ステータス", value=status.get("status", "unknown"), inline=True)
                embed.add_field(
                    name="🧪 テスト結果",
                    value="✅ 成功" if status.get("test_response") else "❌ 失敗",
                    inline=False,
                )
            else:
                embed = discord.Embed(title="🤖 OpenAI API診断", colour=discord.Colour.red())
                embed.add_field(name="🔐 API状態", value="❌ 利用不可", inline=False)

                error = status.get("error", "Unknown error")
                classified_error = status.get("classified_error", "")
                suggestion = status.get("suggestion", "")

                embed.add_field(name="❌ エラー詳細", value=f"```{error[:1000]}```", inline=False)
                if classified_error:
                    embed.add_field(name="📝 ユーザー向けメッセージ", value=classified_error, inline=False)
                if suggestion:
                    embed.add_field(name="💡 対処法", value=suggestion, inline=False)

            # Add environment info
            import os

            api_key_status = "✅ 設定済み" if os.getenv("OPENAI_API_KEY") else "❌ 未設定"
            embed.add_field(name="🔑 API Key", value=api_key_status, inline=True)

            embed.set_footer(text="OpenAI API診断 - Issue #92対応")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in _debug_openai: {e}")
            embed = discord.Embed(
                title="🤖 OpenAI API診断",
                description=f"❌ 診断中にエラーが発生しました: {e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="stats", description="📊 システムメトリクスとパフォーマンス統計を表示")
    async def stats(self, interaction: discord.Interaction):
        """Display system metrics and performance statistics."""
        if not await self._check_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ この機能を使用する権限がありません。管理者権限が必要です。", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # Phase4Monitorサービスを取得
            from ..services import Phase4Monitor, ServiceNotFoundError

            try:
                phase4_monitor = self.bot.service_container.get_service(Phase4Monitor)
            except ServiceNotFoundError:
                embed = discord.Embed(
                    title="❌ システムメトリクス",
                    description="Phase4Monitor サービスが利用できません",
                    colour=discord.Colour.red(),
                )
                await interaction.followup.send(embed=embed)
                return

            # ダッシュボードデータを取得
            dashboard_data = await phase4_monitor.get_dashboard_data()
            current_snapshot = dashboard_data.get("current", {})

            # メイン統計情報Embed
            embed = discord.Embed(
                title="📊 システムメトリクス & パフォーマンス統計",
                description="PKM機能とシステム全体の監視状況",
                colour=discord.Colour.blue(),
            )

            # トークン使用量
            token_usage = current_snapshot.get("token_usage", {})
            monthly_usage = token_usage.get("monthly_usage", {})
            if monthly_usage:
                embed.add_field(
                    name="🎯 トークン使用状況",
                    value=(
                        f"月間使用量: {monthly_usage.get('current_monthly_tokens', 0):,} tokens\n"
                        f"月間制限: {monthly_usage.get('monthly_limit', 0):,} tokens\n"
                        f"使用率: {monthly_usage.get('monthly_usage_percentage', 0):.1f}%"
                    ),
                    inline=False,
                )

            # メモリ使用量
            memory_usage = current_snapshot.get("memory_usage", {})
            current_memory = memory_usage.get("current_usage", {})
            if current_memory:
                embed.add_field(
                    name="💾 メモリ使用状況",
                    value=(
                        f"現在の使用量: {current_memory.get('current_mb', 0):.1f} MB\n"
                        f"GC必要: {'はい' if memory_usage.get('should_trigger_gc', False) else 'いいえ'}\n"
                        f"最大使用量: {current_memory.get('peak_mb', 0):.1f} MB"
                    ),
                    inline=True,
                )

            # PKMパフォーマンス
            pkm_performance = current_snapshot.get("pkm_performance", {})
            pkm_summary = pkm_performance.get("pkm_summary", {})

            search_stats = pkm_summary.get("search_engine", {})
            knowledge_stats = pkm_summary.get("knowledge_manager", {})

            if search_stats:
                embed.add_field(
                    name="🔍 検索エンジン (過去1時間)",
                    value=(
                        f"クエリ数: {search_stats.get('query_count', 0)}\n"
                        f"平均応答時間: {search_stats.get('avg_query_time', 0):.3f}s\n"
                        f"平均結果数: {search_stats.get('avg_result_count', 0):.1f}"
                    ),
                    inline=True,
                )

            if knowledge_stats:
                embed.add_field(
                    name="🧠 ナレッジマネージャー (過去1時間)",
                    value=(
                        f"操作数: {knowledge_stats.get('operation_count', 0)}\n"
                        f"成功率: {knowledge_stats.get('success_rate', 0):.1%}\n"
                        f"平均処理時間: {knowledge_stats.get('avg_processing_time', 0):.3f}s"
                    ),
                    inline=True,
                )

            # システム健全性
            system_health = current_snapshot.get("system_health", {})
            db_health = system_health.get("database", {})

            if db_health:
                db_status = db_health.get("status", "unknown")
                embed.add_field(
                    name="🗄️ データベース状態",
                    value=(
                        f"状態: {'✅ 正常' if db_status == 'healthy' else '❌ エラー'}\n"
                        f"接続テスト: {'成功' if db_health.get('connection_test', False) else '失敗'}\n"
                        f"クエリ時間: {db_health.get('query_time', 0):.3f}s"
                    ),
                    inline=True,
                )

            # API監視状態
            api_status = dashboard_data.get("api_status", {})
            if api_status:
                fallback_level = api_status.get("fallback_level", "unknown")
                monitoring_active = api_status.get("monitoring_active", False)

                embed.add_field(
                    name="🚨 API監視状態",
                    value=(
                        f"監視状態: {'🟢 稼働中' if monitoring_active else '🔴 停止'}\n"
                        f"フォールバックレベル: {fallback_level}\n"
                        f"最終更新: {dashboard_data.get('last_update', 'N/A')}"
                    ),
                    inline=False,
                )

            embed.set_footer(text=f"最終更新: {current_snapshot.get('timestamp', 'N/A')}")

            # 追加の詳細情報ボタン付きView
            view = StatsDetailView(phase4_monitor)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Stats command error: {e}")
            embed = discord.Embed(
                title="❌ システムメトリクス",
                description=f"統計情報の取得中にエラーが発生しました: {e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)


class StatsDetailView(discord.ui.View):
    """詳細なシステム統計情報の表示用View."""

    def __init__(self, phase4_monitor):
        super().__init__(timeout=300.0)  # 5分でタイムアウト
        self.phase4_monitor = phase4_monitor

    @discord.ui.button(label="📈 履歴データ", style=discord.ButtonStyle.secondary)
    async def show_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        """過去1時間のメトリクス履歴を表示."""
        await interaction.response.defer()

        try:
            history_data = await self.phase4_monitor.get_metrics_history(hours=1)

            if not history_data:
                embed = discord.Embed(
                    title="📈 履歴データ",
                    description="履歴データが見つかりませんでした",
                    colour=discord.Colour.orange(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 過去1時間の統計を計算
            token_usages = []
            memory_usages = []
            search_counts = []

            for snapshot in history_data[-12:]:  # 最新12個（約1時間分）
                token_usage = snapshot.get("token_usage", {}).get("monthly_usage", {})
                if token_usage:
                    token_usages.append(token_usage.get("monthly_usage_percentage", 0))

                memory_usage = snapshot.get("memory_usage", {}).get("current_usage", {})
                if memory_usage:
                    memory_usages.append(memory_usage.get("current_mb", 0))

                pkm_perf = snapshot.get("pkm_performance", {}).get("pkm_summary", {})
                search_engine = pkm_perf.get("search_engine", {})
                if search_engine:
                    search_counts.append(search_engine.get("query_count", 0))

            embed = discord.Embed(
                title="📈 システム履歴データ (過去1時間)",
                colour=discord.Colour.green(),
            )

            if token_usages:
                avg_token_usage = sum(token_usages) / len(token_usages)
                embed.add_field(
                    name="🎯 トークン使用率推移",
                    value=(
                        f"平均: {avg_token_usage:.1f}%\n"
                        f"最新: {token_usages[-1]:.1f}%\n"
                        f"データポイント: {len(token_usages)}"
                    ),
                    inline=True,
                )

            if memory_usages:
                avg_memory = sum(memory_usages) / len(memory_usages)
                max_memory = max(memory_usages)
                embed.add_field(
                    name="💾 メモリ使用量推移",
                    value=(
                        f"平均: {avg_memory:.1f} MB\n"
                        f"最大: {max_memory:.1f} MB\n"
                        f"最新: {memory_usages[-1]:.1f} MB"
                    ),
                    inline=True,
                )

            if search_counts:
                total_searches = sum(search_counts)
                embed.add_field(
                    name="🔍 検索活動",
                    value=(
                        f"総クエリ数: {total_searches}\n"
                        f"平均/時間: {total_searches/max(1, len(search_counts)):.1f}\n"
                        f"最新時間: {search_counts[-1] if search_counts else 0}"
                    ),
                    inline=True,
                )

            embed.set_footer(text=f"履歴データ数: {len(history_data)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(
                title="❌ 履歴データエラー",
                description=f"履歴データの取得中にエラー: {e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔧 システム詳細", style=discord.ButtonStyle.secondary)
    async def show_system_details(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """詳細なシステム情報を表示."""
        await interaction.response.defer()

        try:
            # Phase4Monitorのヘルスチェック
            health_check = await self.phase4_monitor.health_check()

            embed = discord.Embed(
                title="🔧 システム詳細情報",
                colour=discord.Colour.blue(),
            )

            # Phase4Monitor自体の状態
            status = health_check.get("status", "unknown")
            embed.add_field(
                name="🤖 Phase4Monitor状態",
                value=(
                    f"状態: {'✅ 正常' if status == 'healthy' else '❌ エラー'}\n"
                    f"監視活動: {'🟢 稼働中' if health_check.get('monitoring_active', False) else '🔴 停止'}\n"
                    f"履歴サイズ: {health_check.get('metric_history_size', 0)}"
                ),
                inline=False,
            )

            # PKMメトリクス詳細
            pkm_metrics = health_check.get("pkm_metrics", {})
            if pkm_metrics:
                embed.add_field(
                    name="📊 PKMメトリクス詳細",
                    value=(
                        f"検索クエリ履歴: {pkm_metrics.get('search_queries', 0)}\n"
                        f"ナレッジ操作履歴: {pkm_metrics.get('knowledge_operations', 0)}\n"
                        f"ChromaDB操作履歴: {pkm_metrics.get('chromadb_operations', 0)}\n"
                        f"DB操作履歴: {pkm_metrics.get('database_operations', 0)}"
                    ),
                    inline=True,
                )

            # システムの技術情報
            embed.add_field(
                name="🛠️ 技術情報",
                value=("監視間隔: 60秒\n" "履歴保持期間: 24時間\n" "最大履歴サイズ: 1440エントリ\n" "メトリクス自動収集: 有効"),
                inline=True,
            )

            embed.set_footer(text=f"ヘルスチェック実行時間: {health_check.get('timestamp', 'N/A')}")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(
                title="❌ システム詳細エラー",
                description=f"システム情報の取得中にエラー: {e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 更新", style=discord.ButtonStyle.primary)
    async def refresh_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """統計情報を強制更新."""
        await interaction.response.defer()

        try:
            # 現在のスナップショットを強制取得
            current_snapshot = await self.phase4_monitor.get_current_snapshot()

            embed = discord.Embed(
                title="🔄 統計情報更新完了",
                description="最新のシステムメトリクスを取得しました",
                colour=discord.Colour.green(),
            )

            # 簡易サマリー表示
            token_usage = current_snapshot.get("token_usage", {}).get("monthly_usage", {})
            if token_usage:
                embed.add_field(
                    name="🎯 更新後のトークン使用率",
                    value=f"{token_usage.get('monthly_usage_percentage', 0):.1f}%",
                    inline=True,
                )

            memory_usage = current_snapshot.get("memory_usage", {}).get("current_usage", {})
            if memory_usage:
                embed.add_field(
                    name="💾 更新後のメモリ使用量",
                    value=f"{memory_usage.get('current_mb', 0):.1f} MB",
                    inline=True,
                )

            embed.set_footer(text=f"更新時刻: {current_snapshot.get('timestamp', 'N/A')}")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(
                title="❌ 更新エラー",
                description=f"統計情報の更新中にエラー: {e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


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
