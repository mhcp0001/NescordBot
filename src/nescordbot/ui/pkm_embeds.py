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

    @staticmethod
    def create_link_suggestions(
        target_note: Dict[str, Any], suggestions: List[Dict[str, Any]]
    ) -> discord.Embed:
        """Embed for link suggestions."""
        embed = discord.Embed(
            title="🔗 リンク候補",
            description=f"**{target_note.get('title', 'Unknown')}** への推奨リンク",
            color=PKMEmbed.COLOR_INFO,
        )

        if not suggestions:
            embed.add_field(name="結果", value="類似度の高いノートが見つかりませんでした。", inline=False)
        else:
            suggestions_text = ""
            for i, suggestion in enumerate(suggestions[:5], 1):
                similarity = suggestion.get("similarity_score", 0) * 100
                title = suggestion.get("title", "Unknown")
                reasons = ", ".join(suggestion.get("similarity_reasons", []))

                suggestions_text += f"**{i}.** {title}\n"
                suggestions_text += f"   • 類似度: {similarity:.1f}%\n"
                if reasons:
                    suggestions_text += f"   • 理由: {reasons}\n"
                suggestions_text += "\n"

            embed.add_field(name="候補ノート", value=suggestions_text.strip(), inline=False)

        embed.set_footer(text="[[title]] 形式でリンクを作成できます")
        return embed

    @staticmethod
    def create_link_validation_summary(validation_result) -> discord.Embed:
        """Embed for overall link validation results."""
        is_healthy = validation_result.is_healthy()

        embed = discord.Embed(
            title="🔍 リンク検証結果",
            description="ナレッジベース全体のリンク整合性",
            color=PKMEmbed.COLOR_SUCCESS if is_healthy else PKMEmbed.COLOR_WARNING,
        )

        # Summary statistics
        embed.add_field(
            name="📊 統計",
            value=(
                f"総ノート数: **{validation_result.total_notes}**\n"
                f"総リンク数: **{validation_result.total_links}**"
            ),
            inline=True,
        )

        # Issues found
        issues = []
        if validation_result.broken_links:
            issues.append(f"❌ 破損リンク: {len(validation_result.broken_links)}")
        if validation_result.orphan_notes:
            issues.append(f"🏝️ 孤立ノート: {len(validation_result.orphan_notes)}")
        if validation_result.circular_links:
            issues.append(f"🔄 循環リンク: {len(validation_result.circular_links)}")
        if validation_result.duplicate_links:
            issues.append(f"📋 重複リンク: {len(validation_result.duplicate_links)}")

        embed.add_field(
            name="🚨 問題", value="\n".join(issues) if issues else "問題は見つかりませんでした ✅", inline=True
        )

        # Health status
        status_emoji = "✅" if is_healthy else "⚠️"
        status_text = "健全" if is_healthy else "要改善"

        embed.add_field(name="💊 健全性", value=f"{status_emoji} {status_text}", inline=True)

        if validation_result.validation_time:
            embed.set_footer(text=f"検証実行時刻: {validation_result.validation_time}")

        return embed

    @staticmethod
    def create_note_link_validation(
        note: Dict[str, Any], validation_result: Dict[str, Any]
    ) -> discord.Embed:
        """Embed for specific note link validation."""
        embed = discord.Embed(
            title="🔗 ノートリンク検証",
            description=f"**{note.get('title', 'Unknown')}** のリンク状況",
            color=PKMEmbed.COLOR_INFO
            if validation_result.get("total_broken", 0) == 0
            else PKMEmbed.COLOR_WARNING,
        )

        # Link statistics
        outgoing = validation_result.get("outgoing_links", {})
        incoming = validation_result.get("incoming_links", {})

        embed.add_field(
            name="📤 発信リンク",
            value=(
                f"有効: {len(outgoing.get('valid', []))}\n" f"破損: {len(outgoing.get('broken', []))}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📥 被参照",
            value=(
                f"有効: {len(incoming.get('valid', []))}\n" f"破損: {len(incoming.get('broken', []))}"
            ),
            inline=True,
        )

        # Status
        is_orphan = validation_result.get("is_orphan", False)
        total_broken = validation_result.get("total_broken", 0)

        if is_orphan:
            status = "🏝️ 孤立"
        elif total_broken > 0:
            status = f"⚠️ 破損リンク {total_broken} 件"
        else:
            status = "✅ 正常"

        embed.add_field(name="状態", value=status, inline=True)

        return embed

    @staticmethod
    def create_centrality_analysis(central_notes: List[Dict[str, Any]]) -> discord.Embed:
        """Embed for centrality analysis results."""
        embed = discord.Embed(
            title="⭐ 中心性分析", description="ナレッジグラフで最も重要なノート", color=PKMEmbed.COLOR_INFO
        )

        if not central_notes:
            embed.add_field(name="結果", value="中心性の高いノートが見つかりませんでした。", inline=False)
        else:
            notes_text = ""
            for i, note in enumerate(central_notes[:10], 1):
                title = note.get("title", "Unknown")
                score = note.get("centrality_score", 0) * 100
                in_degree = note.get("in_degree", 0)
                out_degree = note.get("out_degree", 0)

                notes_text += f"**{i}.** {title}\n"
                notes_text += f"   • 中心性: {score:.1f}%\n"
                notes_text += f"   • 被参照: {in_degree} | 参照: {out_degree}\n\n"

            embed.add_field(name="重要ノート", value=notes_text.strip(), inline=False)

        embed.set_footer(text="中心性スコア = PageRank + 媒介中心性 + 次数中心性")
        return embed

    @staticmethod
    def create_cluster_analysis(clusters) -> discord.Embed:
        """Embed for cluster analysis results."""
        embed = discord.Embed(
            title="🗂️ クラスター分析", description="関連ノートのグループ", color=PKMEmbed.COLOR_INFO
        )

        if not clusters:
            embed.add_field(name="結果", value="十分なサイズのクラスターが見つかりませんでした。", inline=False)
        else:
            clusters_text = ""
            for i, cluster in enumerate(clusters[:5], 1):
                size = cluster.size
                density = cluster.density * 100
                representative = cluster.representative_note or "Unknown"

                clusters_text += f"**クラスター {i}**\n"
                clusters_text += f"   • サイズ: {size} ノート\n"
                clusters_text += f"   • 密度: {density:.1f}%\n"
                clusters_text += f"   • 代表: {representative}\n\n"

            embed.add_field(name="発見されたクラスター", value=clusters_text.strip(), inline=False)

        embed.set_footer(text="密度 = 実際のリンク数 / 可能な最大リンク数")
        return embed

    @staticmethod
    def create_graph_metrics(metrics: Dict[str, Any]) -> discord.Embed:
        """Embed for graph metrics."""
        embed = discord.Embed(
            title="📈 グラフ統計", description="ナレッジベース全体の構造分析", color=PKMEmbed.COLOR_INFO
        )

        # Basic metrics
        embed.add_field(
            name="📊 基本情報",
            value=(
                f"ノード数: **{metrics.get('nodes', 0)}**\n"
                f"エッジ数: **{metrics.get('edges', 0)}**\n"
                f"密度: **{metrics.get('density', 0):.3f}**"
            ),
            inline=True,
        )

        # Connectivity
        embed.add_field(
            name="🔗 接続性",
            value=(
                f"コンポーネント数: **{metrics.get('connected_components', 0)}**\n"
                f"最大成分サイズ: **{metrics.get('largest_component_size', 0)}**\n"
                f"平均経路長: **{metrics.get('average_path_length', 0):.2f}**"
            ),
            inline=True,
        )

        # Degree statistics
        embed.add_field(
            name="📈 次数統計",
            value=(
                f"平均次数: **{metrics.get('average_degree', 0):.2f}**\n"
                f"最大次数: **{metrics.get('max_degree', 0)}**\n"
                f"クラスタリング: **{metrics.get('average_clustering', 0):.3f}**"
            ),
            inline=True,
        )

        embed.set_footer(text="グラフ理論に基づく構造分析")
        return embed

    @staticmethod
    def create_path_analysis(
        from_note: Dict[str, Any], to_note: Dict[str, Any], path_notes: List[Dict[str, Any]]
    ) -> discord.Embed:
        """Embed for path analysis results."""
        embed = discord.Embed(
            title="🛤️ 経路分析",
            description=f"**{from_note.get('title', 'Unknown')}** → "
            f"**{to_note.get('title', 'Unknown')}**",
            color=PKMEmbed.COLOR_INFO,
        )

        if len(path_notes) <= 2:
            embed.add_field(name="直接経路", value="2つのノートは直接リンクしています。", inline=False)
        else:
            path_text = ""
            for i, note in enumerate(path_notes):
                title = note.get("title", "Unknown")
                if i == 0:
                    path_text += f"🏁 **{title}**\n"
                elif i == len(path_notes) - 1:
                    path_text += f"🎯 **{title}**\n"
                else:
                    path_text += f"   ↓\n{i}. {title}\n"

            embed.add_field(
                name=f"最短経路 ({len(path_notes)} ステップ)", value=path_text.strip(), inline=False
            )

        embed.set_footer(text="リンクの強さは考慮されていません")
        return embed
