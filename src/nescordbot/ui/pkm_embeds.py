"""Standardized embed formats for PKM functionality."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import discord

from ..services.search_engine import SearchResult


class PKMEmbed:
    """Factory class for PKM-related embeds with consistent styling."""

    # Color scheme
    COLOR_SUCCESS = discord.Color.green()
    COLOR_INFO = discord.Color.blue()
    COLOR_WARNING = discord.Color.orange()
    COLOR_ERROR = discord.Color.red()
    COLOR_SECONDARY = discord.Color.greyple()

    @staticmethod
    def note_created(
        note_id: str, title: str, created_at: datetime, note_type: str = "fleeting"
    ) -> discord.Embed:
        """Embed for successful note creation."""
        embed = discord.Embed(
            title="📝 ノート作成完了",
            description=f"**{title}**",
            color=PKMEmbed.COLOR_SUCCESS,
            timestamp=created_at,
        )
        embed.add_field(name="ノートID", value=f"`{note_id}`", inline=True)
        embed.add_field(name="タイプ", value=note_type.title(), inline=True)
        embed.add_field(name="作成日時", value=f"<t:{int(created_at.timestamp())}:f>", inline=True)
        embed.set_footer(text="ノートが正常に保存されました")
        return embed

    @staticmethod
    def search_results(
        results: List[SearchResult], query: str, page: int, total_pages: int, total_results: int
    ) -> discord.Embed:
        """Embed for search results display."""
        embed = discord.Embed(
            title=f"🔍 検索結果: {query}",
            description=f"**{total_results}件**の結果が見つかりました",
            color=PKMEmbed.COLOR_INFO,
        )

        if results:
            results_text = ""
            start_idx = page * 3
            for i, result in enumerate(results[:3], 1):
                score_bar = "█" * int(result.score * 10) + "░" * (10 - int(result.score * 10))
                results_text += (
                    f"**{start_idx + i}. {result.title}**\n"
                    f"スコア: {score_bar} `{result.score:.3f}`\n"
                    f"タイプ: {result.source} | 作成: <t:{int(result.created_at.timestamp())}:d>\n"
                    f"```{result.content[:100]}{'...' if len(result.content) > 100 else ''}```\n"
                )
            embed.description = results_text
        else:
            embed.description = "検索結果が見つかりませんでした。"
            embed.colour = PKMEmbed.COLOR_WARNING

        embed.set_footer(text=f"ページ {page + 1}/{total_pages} | 検索時間: {query}")
        return embed

    @staticmethod
    def note_list(
        notes: List[Dict[str, Any]],
        page: int,
        total_pages: int,
        total_notes: int,
        sort_by: str,
        filter_type: str = "all",
    ) -> discord.Embed:
        """Embed for note list display."""
        embed = discord.Embed(
            title="📚 ノート一覧", description=f"**{total_notes}件**のノートがあります", color=PKMEmbed.COLOR_INFO
        )

        if notes:
            notes_text = ""
            start_idx = page * 5
            for i, note in enumerate(notes[:5], 1):
                # タグ表示
                tags_str = ""
                if note.get("tags"):
                    try:
                        if isinstance(note["tags"], str):
                            import json

                            tags = (
                                json.loads(note["tags"])
                                if note["tags"].startswith("[")
                                else note["tags"].split(",")
                            )
                        else:
                            tags = note["tags"]
                        tags_str = " ".join([f"`#{tag.strip()}`" for tag in tags[:3]])
                        if len(tags) > 3:
                            tags_str += f" +{len(tags)-3}"
                    except (json.JSONDecodeError, ValueError, TypeError):
                        tags_str = ""

                # 更新日時
                updated_str = ""
                if note.get("updated_at"):
                    try:
                        if isinstance(note["updated_at"], str):
                            updated_time = datetime.fromisoformat(note["updated_at"])
                        else:
                            updated_time = note["updated_at"]
                        updated_str = f"<t:{int(updated_time.timestamp())}:R>"
                    except (ValueError, TypeError):
                        updated_str = "不明"

                notes_text += (
                    f"**{start_idx + i}. {note.get('title', 'タイトルなし')}**\n"
                    f"タイプ: `{note.get('content_type', 'unknown')}` | 更新: {updated_str}\n"
                )
                if tags_str:
                    notes_text += f"タグ: {tags_str}\n"
                notes_text += "\n"

            embed.description = notes_text
        else:
            embed.description = "ノートが見つかりませんでした。"
            embed.colour = PKMEmbed.COLOR_WARNING

        filter_text = f"フィルタ: {filter_type}" if filter_type != "all" else "全て表示"
        embed.set_footer(text=f"ページ {page + 1}/{total_pages} | ソート: {sort_by} | {filter_text}")
        return embed

    @staticmethod
    def note_detail(note: Dict[str, Any]) -> discord.Embed:
        """Embed for detailed note view."""
        embed = discord.Embed(
            title=f"📄 {note.get('title', 'タイトルなし')}",
            description=note.get("content", "コンテンツなし"),
            color=PKMEmbed.COLOR_INFO,
        )

        # メタデータ
        embed.add_field(name="ノートID", value=f"`{note.get('id', 'unknown')}`", inline=True)
        embed.add_field(name="タイプ", value=note.get("content_type", "unknown").title(), inline=True)

        # 日時情報
        if note.get("created_at"):
            try:
                if isinstance(note["created_at"], str):
                    created_time = datetime.fromisoformat(note["created_at"])
                else:
                    created_time = note["created_at"]
                embed.add_field(
                    name="作成日時", value=f"<t:{int(created_time.timestamp())}:f>", inline=True
                )
            except (ValueError, TypeError):
                pass

        # タグ情報
        if note.get("tags"):
            try:
                if isinstance(note["tags"], str):
                    import json

                    tags = (
                        json.loads(note["tags"])
                        if note["tags"].startswith("[")
                        else note["tags"].split(",")
                    )
                else:
                    tags = note["tags"]
                tags_str = " ".join([f"`#{tag.strip()}`" for tag in tags])
                embed.add_field(name="タグ", value=tags_str or "なし", inline=False)
            except (json.JSONDecodeError, ValueError, TypeError):
                embed.add_field(name="タグ", value="なし", inline=False)

        return embed

    @staticmethod
    def error(message: str, suggestion: Optional[str] = None) -> discord.Embed:
        """Embed for error messages."""
        embed = discord.Embed(title="❌ エラー", description=message, color=PKMEmbed.COLOR_ERROR)

        if suggestion:
            embed.add_field(name="💡 解決方法", value=suggestion, inline=False)

        embed.set_footer(text="問題が続く場合は管理者にお問い合わせください")
        return embed

    @staticmethod
    def success(title: str, description: str) -> discord.Embed:
        """Embed for success messages."""
        embed = discord.Embed(
            title=f"✅ {title}", description=description, color=PKMEmbed.COLOR_SUCCESS
        )
        return embed

    @staticmethod
    def info(title: str, description: str) -> discord.Embed:
        """Embed for informational messages."""
        embed = discord.Embed(
            title=f"ℹ️ {title}", description=description, color=PKMEmbed.COLOR_INFO
        )
        return embed

    @staticmethod
    def loading(message: str = "処理中...") -> discord.Embed:
        """Embed for loading/processing states."""
        embed = discord.Embed(title="⏳ 処理中", description=message, color=PKMEmbed.COLOR_SECONDARY)
        return embed
