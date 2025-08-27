"""PKM (Personal Knowledge Management) Cog for Discord commands."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..services import (
    KnowledgeManager,
    KnowledgeManagerError,
    SearchEngine,
    SearchEngineError,
    SearchFilters,
    SearchQueryError,
    ServiceContainer,
)
from ..services.search_engine import SearchMode
from ..ui.pkm_embeds import PKMEmbed
from ..ui.pkm_views import PKMHelpView, PKMListView, PKMNoteView, SearchResultView

logger = logging.getLogger(__name__)

# Constants
MAX_TITLE_LENGTH = 100
MAX_CONTENT_LENGTH = 4000
MAX_QUERY_LENGTH = 200
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 20
MIN_LIST_LIMIT = 1
MAX_LIST_LIMIT = 50
COMMAND_TIMEOUT = 30  # seconds


class PKMCog(commands.Cog):
    """Discord commands for Personal Knowledge Management."""

    def __init__(self, bot: commands.Bot):
        """Initialize PKMCog.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.knowledge_manager: Optional[KnowledgeManager] = None
        self.search_engine: Optional[SearchEngine] = None
        self._initialized = False

        logger.info("PKMCog initialized")

    async def initialize_services(self) -> None:
        """Initialize required services from ServiceContainer."""
        if self._initialized:
            return

        try:
            # ServiceContainer経由でサービス取得
            service_container = getattr(self.bot, "service_container", None)
            if not service_container:
                raise RuntimeError("ServiceContainer not found in bot instance")

            # Type assertion for mypy
            assert isinstance(service_container, ServiceContainer)

            # サービス取得
            self.knowledge_manager = service_container.get_service(KnowledgeManager)
            self.search_engine = service_container.get_service(SearchEngine)

            # サービス初期化確認
            await self.knowledge_manager.initialize()

            self._initialized = True
            logger.info("PKMCog services initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PKMCog services: {e}")
            raise

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize services when bot is ready."""
        try:
            await self.initialize_services()
        except Exception as e:
            logger.error(f"PKMCog initialization failed: {e}")

    # PKM Command Group
    pkm_group = app_commands.Group(name="pkm", description="Personal Knowledge Management commands")

    @pkm_group.command(name="note", description="新しいノートを作成")
    @app_commands.describe(
        title="ノートのタイトル（1-100文字）",
        content="ノートの本文（1-4000文字）",
        tags="タグ（カンマ区切り、任意）",
        note_type="ノートタイプ（デフォルト: fleeting）",
    )
    @app_commands.choices(
        note_type=[
            app_commands.Choice(name="一時ノート", value="fleeting"),
            app_commands.Choice(name="永続ノート", value="permanent"),
            app_commands.Choice(name="リンク", value="link"),
        ]
    )
    async def note_command(
        self,
        interaction: discord.Interaction,
        title: app_commands.Range[str, 1, MAX_TITLE_LENGTH],
        content: app_commands.Range[str, 1, MAX_CONTENT_LENGTH],
        tags: Optional[str] = None,
        note_type: Optional[str] = "fleeting",
    ) -> None:
        """Create a new note.

        Args:
            interaction: Discord interaction
            title: Note title
            content: Note content
            tags: Comma-separated tags (optional)
            note_type: Type of note (fleeting/permanent/link)
        """
        # Service initialization check
        if not self._initialized:
            try:
                await self.initialize_services()
            except Exception as e:
                logger.error(f"Service initialization failed: {e}")
                embed = PKMEmbed.error("サービス初期化エラー", "PKM機能の初期化に失敗しました。管理者にお問い合わせください。")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        # Immediate defer to avoid 3-second timeout
        await interaction.response.defer()

        user_id = str(interaction.user.id)

        try:
            # Process tags
            tags_list = []
            if tags:
                tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
                # Validate tags (alphanumeric + Japanese only)
                for tag in tags_list:
                    if not re.match(r"^[\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+$", tag):
                        embed = PKMEmbed.error("無効なタグ", f"タグ「{tag}」に無効な文字が含まれています。英数字と日本語のみ使用できます。")
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return

            # Create note
            assert self.knowledge_manager is not None
            note_id = await asyncio.wait_for(
                self.knowledge_manager.create_note(
                    title=title,
                    content=content,
                    tags=tags_list,
                    source_type="manual",
                    user_id=user_id,
                ),
                timeout=COMMAND_TIMEOUT,
            )

            # Success response
            created_at = datetime.now()
            embed = PKMEmbed.note_created(
                note_id=note_id,
                title=title,
                created_at=created_at,
                note_type=note_type or "fleeting",
            )

            # Get full note data for view
            note_data = {
                "id": note_id,
                "title": title,
                "content": content,
                "tags": tags_list,
                "created_at": created_at.isoformat(),
            }
            view = PKMNoteView(note_data, self.knowledge_manager, user_id)
            await interaction.followup.send(embed=embed, view=view)

            logger.info(
                f"Note created: user={user_id}, note_id={note_data['id']}, title='{title[:50]}...'"
            )

        except asyncio.TimeoutError:
            logger.warning(f"Note creation timeout: user={user_id}, title='{title[:50]}...'")
            embed = PKMEmbed.error("処理がタイムアウトしました", "ネットワーク接続を確認して、再度お試しください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except KnowledgeManagerError as e:
            logger.error(f"Knowledge manager error in note creation: {e}")
            embed = PKMEmbed.error("ノート作成に失敗しました", "データベースエラーが発生しました。しばらく待ってから再試行してください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Unexpected error in note creation: {e}")
            embed = PKMEmbed.error("予期しないエラーが発生しました", "管理者にお問い合わせください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @pkm_group.command(name="search", description="ノートを検索")
    @app_commands.describe(
        query="検索クエリ（1-200文字）",
        limit="検索結果数（1-20、デフォルト: 5）",
        note_type="ノートタイプフィルタ（all/permanent/fleeting）",
        min_score="最小スコア（0.0-1.0、デフォルト: 0.1）",
        search_mode="検索モード（hybrid/vector/keyword、デフォルト: hybrid）",
        alpha="ベクトル重み（0.0-1.0、デフォルト: 0.7）",
    )
    @app_commands.choices(
        note_type=[
            app_commands.Choice(name="全て", value="all"),
            app_commands.Choice(name="永続ノート", value="permanent"),
            app_commands.Choice(name="一時ノート", value="fleeting"),
            app_commands.Choice(name="リンク", value="link"),
        ],
        search_mode=[
            app_commands.Choice(name="ハイブリッド（推奨）", value="hybrid"),
            app_commands.Choice(name="ベクトル検索", value="vector"),
            app_commands.Choice(name="キーワード検索", value="keyword"),
        ],
    )
    async def search_command(
        self,
        interaction: discord.Interaction,
        query: app_commands.Range[str, 1, MAX_QUERY_LENGTH],
        limit: Optional[app_commands.Range[int, MIN_SEARCH_LIMIT, MAX_SEARCH_LIMIT]] = 5,
        note_type: Optional[str] = "all",
        min_score: Optional[app_commands.Range[float, 0.0, 1.0]] = 0.1,
        search_mode: Optional[str] = "hybrid",
        alpha: Optional[app_commands.Range[float, 0.0, 1.0]] = None,
    ) -> None:
        """Search notes with hybrid search.

        Args:
            interaction: Discord interaction
            query: Search query
            limit: Maximum number of results
            note_type: Filter by note type
            min_score: Minimum relevance score
        """
        # Service initialization check
        if not self._initialized:
            try:
                await self.initialize_services()
            except Exception as e:
                logger.error(f"Service initialization failed: {e}")
                embed = PKMEmbed.error("サービス初期化エラー", "PKM機能の初期化に失敗しました。管理者にお問い合わせください。")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        # Immediate defer to avoid 3-second timeout
        await interaction.response.defer()

        user_id = str(interaction.user.id)

        try:
            # Build search filters
            filters = SearchFilters(
                user_id=user_id,
                content_type=note_type if note_type != "all" else None,
                min_score=min_score,
            )

            # Convert search mode string to enum
            try:
                mode = SearchMode(search_mode)
            except ValueError:
                mode = SearchMode.HYBRID

            # Perform search
            assert self.search_engine is not None
            search_results = await asyncio.wait_for(
                self.search_engine.hybrid_search(
                    query=query, mode=mode, alpha=alpha, limit=limit, filters=filters
                ),
                timeout=COMMAND_TIMEOUT,
            )

            # Display results
            if search_results:
                assert self.knowledge_manager is not None
                view = SearchResultView(
                    search_results=search_results,
                    query=query,
                    knowledge_manager=self.knowledge_manager,
                    user_id=user_id,
                )
                embed = PKMEmbed.search_results(
                    results=search_results[:3],  # First page
                    query=query,
                    page=0,
                    total_pages=max(1, (len(search_results) + 2) // 3),
                    total_results=len(search_results),
                )
                await interaction.followup.send(embed=embed, view=view)
            else:
                embed = PKMEmbed.error("検索結果が見つかりませんでした", "検索クエリを変更するか、最小スコアを下げてみてください。")
                embed.colour = PKMEmbed.COLOR_WARNING
                await interaction.followup.send(embed=embed)

            logger.info(
                f"Search completed: user={user_id}, query='{query[:50]}...', "
                f"results={len(search_results)}"
            )

        except asyncio.TimeoutError:
            logger.warning(f"Search timeout: user={user_id}, query='{query[:50]}...'")
            embed = PKMEmbed.error("検索がタイムアウトしました", "クエリを短くして再試行してください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except SearchQueryError as e:
            logger.warning(f"Invalid search query: user={user_id}, query='{query}', error={e}")
            embed = PKMEmbed.error("無効な検索クエリ", "検索クエリの形式を確認してください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except SearchEngineError as e:
            logger.error(f"Search engine error: user={user_id}, query='{query}', error={e}")
            embed = PKMEmbed.error("検索に失敗しました", "検索システムに問題が発生しました。しばらく待ってから再試行してください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Unexpected error in search: {e}")
            embed = PKMEmbed.error("予期しないエラーが発生しました", "管理者にお問い合わせください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @pkm_group.command(name="list", description="ノート一覧を表示")
    @app_commands.describe(
        limit="表示数（1-50、デフォルト: 10）",
        sort="ソート順（created/updated/title）",
        note_type="タイプフィルタ（all/permanent/fleeting）",
        tag="タグフィルタ（任意）",
    )
    @app_commands.choices(
        sort=[
            app_commands.Choice(name="更新日時（新しい順）", value="updated"),
            app_commands.Choice(name="作成日時（新しい順）", value="created"),
            app_commands.Choice(name="タイトル（昇順）", value="title"),
        ],
        note_type=[
            app_commands.Choice(name="全て", value="all"),
            app_commands.Choice(name="永続ノート", value="permanent"),
            app_commands.Choice(name="一時ノート", value="fleeting"),
            app_commands.Choice(name="リンク", value="link"),
        ],
    )
    async def list_command(
        self,
        interaction: discord.Interaction,
        limit: Optional[app_commands.Range[int, MIN_LIST_LIMIT, MAX_LIST_LIMIT]] = 10,
        sort: Optional[str] = "updated",
        note_type: Optional[str] = "all",
        tag: Optional[str] = None,
    ) -> None:
        """List user's notes.

        Args:
            interaction: Discord interaction
            limit: Maximum number of notes to display
            sort: Sort order (created/updated/title)
            note_type: Filter by note type
            tag: Filter by specific tag
        """
        # Service initialization check
        if not self._initialized:
            try:
                await self.initialize_services()
            except Exception as e:
                logger.error(f"Service initialization failed: {e}")
                embed = PKMEmbed.error("サービス初期化エラー", "PKM機能の初期化に失敗しました。管理者にお問い合わせください。")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        # Immediate defer
        await interaction.response.defer()

        user_id = str(interaction.user.id)

        try:
            # Get notes with filters
            assert self.knowledge_manager is not None
            sort_val = sort or "updated"
            filter_val = note_type or "all"
            limit_val = limit or 10
            notes = await asyncio.wait_for(
                self._get_filtered_notes(user_id, limit_val, sort_val, filter_val, tag),
                timeout=COMMAND_TIMEOUT,
            )

            # Display results
            if notes:
                view = PKMListView(
                    notes=notes,
                    sort_by=sort_val,
                    filter_type=filter_val,
                    knowledge_manager=self.knowledge_manager,
                    user_id=user_id,
                )
                embed = PKMEmbed.note_list(
                    notes=notes[:5],  # First page
                    page=0,
                    total_pages=max(1, (len(notes) + 4) // 5),
                    total_notes=len(notes),
                    sort_by=sort_val,
                    filter_type=filter_val,
                )
                await interaction.followup.send(embed=embed, view=view)
            else:
                embed = PKMEmbed.error("ノートが見つかりませんでした", "まず `/pkm note` コマンドでノートを作成してください。")
                embed.colour = PKMEmbed.COLOR_WARNING
                await interaction.followup.send(embed=embed)

            logger.info(
                f"Notes listed: user={user_id}, count={len(notes)}, sort={sort}, type={note_type}"
            )

        except asyncio.TimeoutError:
            logger.warning(f"List timeout: user={user_id}")
            embed = PKMEmbed.error("一覧取得がタイムアウトしました", "表示数を少なくして再試行してください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except KnowledgeManagerError as e:
            logger.error(f"Knowledge manager error in list: {e}")
            embed = PKMEmbed.error("ノート一覧の取得に失敗しました", "データベースエラーが発生しました。しばらく待ってから再試行してください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Unexpected error in list command: {e}")
            embed = PKMEmbed.error("予期しないエラーが発生しました", "管理者にお問い合わせください。")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @pkm_group.command(name="help", description="PKM機能のヘルプを表示")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Show PKM help information."""
        embed = discord.Embed(
            title="📚 PKM (Personal Knowledge Management) ヘルプ",
            description="あなたの第二の脳として機能するノート管理システムです。",
            color=PKMEmbed.COLOR_INFO,
        )

        embed.add_field(
            name="🏗️ 基本概念",
            value=(
                "• **永続ノート**: 重要な知識やアイデア\n"
                "• **一時ノート**: メモや思考の断片\n"
                "• **リンク**: 外部リソースへの参照\n"
                "• **ハイブリッド検索**: ベクトル+キーワード検索"
            ),
            inline=False,
        )

        embed.add_field(
            name="📖 使用方法",
            value=(
                "1. `/pkm note` でノートを作成\n"
                "2. `/pkm search` で過去のノートを検索\n"
                "3. `/pkm list` でノート一覧を確認"
            ),
            inline=False,
        )

        view = PKMHelpView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _get_filtered_notes(
        self, user_id: str, limit: int, sort: str, note_type: str, tag: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get filtered notes list."""
        assert self.knowledge_manager is not None

        if tag:
            # Tag-based filtering
            notes = await self.knowledge_manager.get_notes_by_tag(tag, limit=limit * 2)
            # Additional filtering by type
            if note_type != "all":
                notes = [n for n in notes if n.get("source_type") == note_type]
            # Limit results
            notes = notes[:limit]
        else:
            # Regular list with user filter
            notes = await self.knowledge_manager.list_notes(
                user_id=user_id,
                source_type=note_type if note_type != "all" else None,
                limit=limit,
            )

        return notes

    @app_commands.command(name="link_suggest", description="ノートのリンク候補を提案します")
    @app_commands.describe(
        note_title="リンク候補を提案するノートのタイトル（部分一致可）",
        max_suggestions="提案する最大数（1-10）",
        min_similarity="最小類似度（0.1-1.0）",
    )
    async def link_suggest_command(
        self,
        interaction: discord.Interaction,
        note_title: str,
        max_suggestions: int = 5,
        min_similarity: float = 0.3,
    ) -> None:
        """Suggest links for a note based on content similarity."""
        if not await self._check_services(interaction):
            return

        try:
            await interaction.response.defer()

            assert self.knowledge_manager is not None, "KnowledgeManager not initialized"

            # Find note by title
            notes = await self.knowledge_manager.search_notes(note_title, limit=5)
            if not notes:
                await interaction.followup.send(f"❌ ノート「{note_title}」が見つかりませんでした。", ephemeral=True)
                return

            # Use the first match
            target_note = notes[0]
            note_id = target_note["id"]

            # Validate parameters
            max_suggestions = max(1, min(10, max_suggestions))
            min_similarity = max(0.1, min(1.0, min_similarity))

            # Get suggestions
            suggestions = await self.knowledge_manager.suggest_links_for_note(
                note_id, max_suggestions, min_similarity
            )

            # Create embed
            embed = PKMEmbed.create_link_suggestions(target_note, suggestions)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Link suggestion failed: {e}")
            await interaction.followup.send(f"❌ リンク提案の取得に失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="link_validate", description="ノートリンクの整合性を検証します")
    @app_commands.describe(note_title="検証するノートのタイトル（省略時は全体検証）")
    async def link_validate_command(
        self, interaction: discord.Interaction, note_title: Optional[str] = None
    ) -> None:
        """Validate note links for broken references."""
        if not await self._check_services(interaction):
            return

        try:
            await interaction.response.defer()

            assert self.knowledge_manager is not None, "KnowledgeManager not initialized"

            if note_title:
                # Validate specific note
                notes = await self.knowledge_manager.search_notes(note_title, limit=1)
                if not notes:
                    await interaction.followup.send(
                        f"❌ ノート「{note_title}」が見つかりませんでした。", ephemeral=True
                    )
                    return

                note_id = notes[0]["id"]
                note_result = await self.knowledge_manager.validate_note_links(note_id)
                embed = PKMEmbed.create_note_link_validation(notes[0], note_result)

            else:
                # Validate all links
                validation_result = await self.knowledge_manager.validate_all_links()
                embed = PKMEmbed.create_link_validation_summary(validation_result)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Link validation failed: {e}")
            await interaction.followup.send(f"❌ リンク検証に失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="link_graph", description="ノートのつながりをグラフで分析します")
    @app_commands.describe(analysis_type="分析タイプ", top_n="上位N件（中心性分析用）")
    @app_commands.choices(
        analysis_type=[
            app_commands.Choice(name="中心性分析（重要なノートを発見）", value="centrality"),
            app_commands.Choice(name="クラスター分析（関連ノートのグループ）", value="clusters"),
            app_commands.Choice(name="グラフ統計（全体の分析）", value="metrics"),
        ]
    )
    async def link_graph_command(
        self, interaction: discord.Interaction, analysis_type: str, top_n: int = 10
    ) -> None:
        """Analyze note connections using graph theory."""
        if not await self._check_services(interaction):
            return

        try:
            await interaction.response.defer()

            assert self.knowledge_manager is not None, "KnowledgeManager not initialized"

            # Validate top_n
            top_n = max(5, min(20, top_n))

            if analysis_type == "centrality":
                # Find most central notes
                central_notes = await self.knowledge_manager.find_central_notes(top_n)
                embed = PKMEmbed.create_centrality_analysis(central_notes)

            elif analysis_type == "clusters":
                # Find note clusters
                clusters = await self.knowledge_manager.find_note_clusters(min_cluster_size=3)
                embed = PKMEmbed.create_cluster_analysis(clusters[:10])  # Show top 10 clusters

            elif analysis_type == "metrics":
                # Get overall graph metrics
                metrics = await self.knowledge_manager.get_graph_metrics()
                embed = PKMEmbed.create_graph_metrics(metrics)

            else:
                await interaction.followup.send("❌ 無効な分析タイプです。", ephemeral=True)
                return

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Graph analysis failed: {e}")
            await interaction.followup.send(f"❌ グラフ分析に失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="link_path", description="2つのノート間の最短経路を検索します")
    @app_commands.describe(from_note="開始ノートのタイトル", to_note="終了ノートのタイトル")
    async def link_path_command(
        self, interaction: discord.Interaction, from_note: str, to_note: str
    ) -> None:
        """Find shortest path between two notes."""
        if not await self._check_services(interaction):
            return

        try:
            await interaction.response.defer()

            assert self.knowledge_manager is not None, "KnowledgeManager not initialized"

            # Find both notes
            from_notes = await self.knowledge_manager.search_notes(from_note, limit=1)
            to_notes = await self.knowledge_manager.search_notes(to_note, limit=1)

            if not from_notes:
                await interaction.followup.send(f"❌ 開始ノート「{from_note}」が見つかりませんでした。", ephemeral=True)
                return

            if not to_notes:
                await interaction.followup.send(f"❌ 終了ノート「{to_note}」が見つかりませんでした。", ephemeral=True)
                return

            from_id = from_notes[0]["id"]
            to_id = to_notes[0]["id"]

            # Find shortest path
            path = await self.knowledge_manager.find_shortest_path(from_id, to_id)

            if path is None:
                embed = discord.Embed(
                    title="🚫 パスが見つかりません",
                    description=f"「{from_notes[0]['title']}」から「{to_notes[0]['title']}」への経路は存在しません。",
                    color=discord.Color.orange(),
                )
            else:
                # Get note details for path
                path_notes = []
                for note_id in path:
                    note = await self.knowledge_manager.get_note(note_id)
                    if note:
                        path_notes.append(note)

                embed = PKMEmbed.create_path_analysis(from_notes[0], to_notes[0], path_notes)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Path finding failed: {e}")
            await interaction.followup.send(f"❌ 経路検索に失敗しました: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(PKMCog(bot))
    logger.info("PKMCog loaded successfully")
