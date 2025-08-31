"""
API Status Cog - API制限状況とフォールバック機能の管理UI.

管理者向けのAPIステータス確認、手動制御、キャッシュ管理コマンドを提供する。
"""

import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..services import APIMonitor, FallbackLevel, ServiceNotFoundError

logger = logging.getLogger(__name__)


class APIStatusView(discord.ui.View):
    """API状態表示用のDiscord UI."""

    def __init__(self, api_monitor: APIMonitor, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.api_monitor = api_monitor

    @discord.ui.button(label="🔄 状態更新", style=discord.ButtonStyle.primary)
    async def refresh_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """API状態を更新して表示."""
        await interaction.response.defer()

        try:
            # 最新状態を取得
            status_data = await self.api_monitor.force_check()

            # 埋め込みメッセージを作成
            embed = self._create_status_embed(status_data)

            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

        except Exception as e:
            logger.error(f"Failed to refresh API status: {e}")
            await interaction.followup.send(f"❌ ステータス更新に失敗しました: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🗑️ キャッシュクリア", style=discord.ButtonStyle.secondary)
    async def clear_cache(self, interaction: discord.Interaction, button: discord.ui.Button):
        """全キャッシュをクリア."""
        await interaction.response.defer()

        try:
            await self.api_monitor.clear_cache()
            await interaction.followup.send("✅ 全キャッシュをクリアしました", ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            await interaction.followup.send(f"❌ キャッシュクリアに失敗しました: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🚨 緊急オーバーライド", style=discord.ButtonStyle.danger)
    async def emergency_override(self, interaction: discord.Interaction, button: discord.ui.Button):
        """緊急時の手動オーバーライドモードを有効化."""
        await interaction.response.send_message(
            "⚠️ 緊急オーバーライドを有効にしますか？\n" "この機能は手動でフォールバックレベルを設定します。",
            view=EmergencyOverrideView(self.api_monitor),
            ephemeral=True,
        )

    def _create_status_embed(self, status_data: dict) -> discord.Embed:
        """ステータス情報からDiscord埋め込みを作成."""
        usage_data = status_data.get("usage_data", {})
        usage_pct = usage_data.get("monthly_usage_percentage", 0)
        current_tokens = usage_data.get("current_monthly_tokens", 0)
        monthly_limit = usage_data.get("monthly_limit", 0)
        fallback_level = status_data.get("fallback_level", "normal")

        # レベルに応じた色設定
        color_map = {
            "normal": discord.Color.green(),
            "limited": discord.Color.yellow(),
            "critical": discord.Color.orange(),
            "emergency": discord.Color.red(),
        }

        embed = discord.Embed(
            title="🔍 API ステータス",
            color=color_map.get(fallback_level, discord.Color.grey()),
            timestamp=datetime.fromisoformat(
                status_data.get("timestamp", datetime.now().isoformat())
            ),
        )

        # 使用量情報
        embed.add_field(
            name="📊 月間使用量",
            value=f"**{usage_pct:.1f}%** ({current_tokens:,} / {monthly_limit:,} tokens)",
            inline=False,
        )

        # フォールバックレベル
        level_emoji = {"normal": "🟢", "limited": "🟡", "critical": "🟠", "emergency": "🔴"}

        embed.add_field(
            name="⚙️ フォールバックレベル",
            value=f"{level_emoji.get(fallback_level, '⚪')} **{fallback_level.upper()}**",
            inline=True,
        )

        # サービス状態
        service_states = status_data.get("service_states", {})
        active_services = sum(1 for active in service_states.values() if active)
        total_services = len(service_states)

        embed.add_field(
            name="🛠️ アクティブサービス", value=f"**{active_services} / {total_services}** サービス", inline=True
        )

        # キャッシュ統計
        cache_stats = status_data.get("cache_stats", {})
        cache_entries = cache_stats.get("total_entries", 0)
        cache_types = len(cache_stats.get("types", {}))

        embed.add_field(
            name="💾 キャッシュ", value=f"**{cache_entries}** エントリ ({cache_types} タイプ)", inline=True
        )

        # サービス詳細
        service_status = []
        for service, active in service_states.items():
            status = "✅" if active else "❌"
            service_status.append(f"{status} {service}")

        if service_status:
            embed.add_field(name="📋 サービス詳細", value="\n".join(service_status), inline=False)

        embed.set_footer(text="最終更新")
        return embed


class EmergencyOverrideView(discord.ui.View):
    """緊急オーバーライド設定用UI."""

    def __init__(self, api_monitor: APIMonitor):
        super().__init__(timeout=60)
        self.api_monitor = api_monitor

    @discord.ui.select(
        placeholder="フォールバックレベルを選択...",
        options=[
            discord.SelectOption(label="Normal", value="normal", emoji="🟢"),
            discord.SelectOption(label="Limited", value="limited", emoji="🟡"),
            discord.SelectOption(label="Critical", value="critical", emoji="🟠"),
            discord.SelectOption(label="Emergency", value="emergency", emoji="🔴"),
        ],
    )
    async def select_level(self, interaction: discord.Interaction, select: discord.ui.Select):
        """フォールバックレベル選択."""
        selected_level = FallbackLevel(select.values[0])

        try:
            await self.api_monitor.emergency_override(selected_level)
            await interaction.response.send_message(
                f"✅ 緊急オーバーライド有効: **{selected_level.value.upper()}**", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ オーバーライド設定に失敗: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🔄 オーバーライド解除", style=discord.ButtonStyle.success)
    async def clear_override(self, interaction: discord.Interaction, button: discord.ui.Button):
        """オーバーライドを解除."""
        try:
            await self.api_monitor.clear_emergency_override()
            await interaction.response.send_message("✅ オーバーライドを解除しました", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ オーバーライド解除に失敗: {str(e)}", ephemeral=True)


class APIStatusCog(commands.Cog):
    """API制限状況管理用のCogクラス."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Cog読み込み時の処理."""
        logger.info("APIStatusCog loaded")

    async def cog_unload(self):
        """Cog読み込み解除時の処理."""
        logger.info("APIStatusCog unloaded")

    def _get_api_monitor(self):
        """APIMonitorサービスを取得."""
        try:
            return self.bot.service_container.get_service(APIMonitor)
        except ServiceNotFoundError:
            raise commands.CommandError("APIMonitor service not available")

    @app_commands.command(name="api_status", description="API使用量とフォールバック状態を表示")
    @app_commands.describe()
    async def api_status(self, interaction: discord.Interaction):
        """API状態を表示するコマンド."""
        # 管理者チェック
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ このコマンドは管理者のみ実行可能です", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            api_monitor = self._get_api_monitor()

            # 現在の状態を取得
            status_data = await api_monitor.force_check()

            # UIビューを作成
            view = APIStatusView(api_monitor)
            embed = view._create_status_embed(status_data)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Failed to get API status: {e}")
            await interaction.followup.send(f"❌ API状態の取得に失敗しました: {str(e)}")

    @app_commands.command(name="api_cache_clear", description="APIフォールバックキャッシュをクリア")
    @app_commands.describe(cache_type="クリアするキャッシュタイプ（省略時は全て）")
    async def api_cache_clear(
        self, interaction: discord.Interaction, cache_type: Optional[str] = None
    ):
        """キャッシュクリアコマンド."""
        # 管理者チェック
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ このコマンドは管理者のみ実行可能です", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            api_monitor = self._get_api_monitor()
            await api_monitor.clear_cache(cache_type)

            cache_desc = cache_type or "全て"
            await interaction.followup.send(f"✅ {cache_desc}のキャッシュをクリアしました")

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            await interaction.followup.send(f"❌ キャッシュクリアに失敗しました: {str(e)}")


async def setup(bot: commands.Bot):
    """Cogセットアップ関数."""
    await bot.add_cog(APIStatusCog(bot))
