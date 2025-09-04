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
from ..ui.pkm_views import (
    EditNoteModal,
    EditNoteSelectionView,
    PKMHelpView,
    PKMListView,
    PKMNoteView,
    SearchResultView,
)

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

    async def _check_services(self, interaction: discord.Interaction) -> bool:
        """Check if services are properly initialized."""
        if not self._initialized or self.knowledge_manager is None:
            await interaction.response.send_message(
                "❌ PKMサービスが初期化されていません。しばらく待ってから再試行してください。", ephemeral=True
            )
            return False
        return True

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

    # Merge command group
    @app_commands.command(name="merge", description="複数のノートを意味的に統合して新しい知見を生成します")
    @app_commands.describe(notes="統合したいノート（1-3個、スペース区切り）", custom_title="統合ノートのカスタムタイトル（オプション）")
    async def merge_command(
        self, interaction: discord.Interaction, notes: str, custom_title: Optional[str] = None
    ) -> None:
        """Interactive note merging with AI suggestions."""
        if not await self._check_services(interaction):
            return

        await interaction.response.defer(thinking=True)

        try:
            # Parse note references
            note_titles = [title.strip() for title in notes.split() if title.strip()]

            if not note_titles:
                await interaction.followup.send(
                    "❌ 統合するノートを1つ以上指定してください。\n" "例: `/merge 会議録2024 プロジェクト要件`", ephemeral=True
                )
                return

            if len(note_titles) > 3:
                await interaction.followup.send("❌ 一度に指定できるノートは最大3個までです。", ephemeral=True)
                return

            # Find matching notes
            selected_notes = []
            assert self.knowledge_manager is not None  # Type guard
            for title_part in note_titles:
                matching_notes = await self.knowledge_manager.search_notes(
                    query=title_part, limit=5
                )

                if not matching_notes:
                    await interaction.followup.send(
                        f"❌ '{title_part}' に該当するノートが見つかりません。", ephemeral=True
                    )
                    return

                # Take the best match
                best_match = matching_notes[0]
                selected_notes.append(best_match)

            # Create merge view with AI suggestions
            assert self.knowledge_manager is not None  # Type guard for mypy
            merge_view = NoteMergeView(
                selected_notes=selected_notes,
                knowledge_manager=self.knowledge_manager,
                custom_title=custom_title,
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
            )

            # Send initial merge interface
            embed = merge_view.create_initial_embed()
            await interaction.followup.send(embed=embed, view=merge_view)

        except Exception as e:
            logger.error(f"Merge command failed: {e}")
            await interaction.followup.send(f"❌ ノート統合に失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="auto-tag", description="AIを使ってノートに自動タグ付け・カテゴリ化を行う")
    @app_commands.describe(
        mode="実行モード: suggest=提案のみ, apply=自動適用, batch=一括処理",
        note_id="特定のノートID（未指定の場合は全ノート対象）",
        max_suggestions="最大提案数（1-10、デフォルト: 5）",
        confidence_threshold="自動適用の信頼度閾値（0.1-1.0、デフォルト: 0.8）",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="提案のみ", value="suggest"),
            app_commands.Choice(name="自動適用", value="apply"),
            app_commands.Choice(name="一括処理", value="batch"),
        ]
    )
    async def auto_tag_command(
        self,
        interaction: discord.Interaction,
        mode: str = "suggest",
        note_id: str = "",
        max_suggestions: int = 5,
        confidence_threshold: float = 0.8,
    ) -> None:
        """AIを使ったノートの自動タグ付け・カテゴリ化機能"""
        if not self._initialized:
            await interaction.response.send_message("❌ サービスが初期化されていません", ephemeral=True)
            return

        try:
            await interaction.response.defer()

            # パラメータ検証
            if max_suggestions < 1 or max_suggestions > 10:
                await interaction.followup.send(
                    "❌ max_suggestions は 1-10 の範囲で指定してください", ephemeral=True
                )
                return

            if confidence_threshold < 0.1 or confidence_threshold > 1.0:
                await interaction.followup.send(
                    "❌ confidence_threshold は 0.1-1.0 の範囲で指定してください", ephemeral=True
                )
                return

            if mode == "suggest":
                await self._handle_tag_suggestion(interaction, note_id, max_suggestions)
            elif mode == "apply":
                await self._handle_tag_application(
                    interaction, note_id, max_suggestions, confidence_threshold
                )
            elif mode == "batch":
                await self._handle_batch_tagging(interaction, max_suggestions, confidence_threshold)

        except Exception as e:
            logger.error(f"Auto-tag command error: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)

    async def _handle_tag_suggestion(
        self, interaction: discord.Interaction, note_id: str, max_suggestions: int
    ) -> None:
        """タグ提案モードの処理"""
        if not self.knowledge_manager:
            await interaction.followup.send("❌ KnowledgeManagerが利用できません", ephemeral=True)
            return

        if note_id:
            # 特定ノートのタグ提案
            note = await self.knowledge_manager.get_note(note_id)
            if not note:
                await interaction.followup.send(f"❌ ノート '{note_id}' が見つかりません", ephemeral=True)
                return

            suggestions = await self.knowledge_manager.suggest_tags_for_content(
                content=note["content"],
                title=note["title"],
                existing_tags=note.get("tags", []),
                max_suggestions=max_suggestions,
            )

            await self._send_tag_suggestions_response(interaction, note, suggestions)
        else:
            # 全ノートから適当に選んでサンプル提案
            notes = await self.knowledge_manager.list_notes(limit=5)
            if not notes:
                await interaction.followup.send("📝 タグ付け可能なノートが見つかりません", ephemeral=True)
                return

            # 最初の数ノートに対してサンプル提案
            embeds = []
            for i, note in enumerate(notes[:3]):  # 最大3つまで
                suggestions = await self.knowledge_manager.suggest_tags_for_content(
                    content=note["content"],
                    title=note["title"],
                    existing_tags=note.get("tags", []),
                    max_suggestions=3,
                )

                if suggestions:
                    embed = discord.Embed(
                        title=f"🏷️ タグ提案サンプル {i+1}",
                        description=f"**ノート**: {note['title'][:50]}"
                        + ("..." if len(note["title"]) > 50 else ""),
                        color=0x00FF00,
                    )

                    for j, suggestion in enumerate(suggestions[:3]):
                        embed.add_field(
                            name=f"{j+1}. {suggestion['tag']}",
                            value=f"信頼度: {suggestion['confidence']:.2f}\n"
                            + f"{suggestion['reason'][:100]}"
                            + ("..." if len(suggestion["reason"]) > 100 else ""),
                            inline=False,
                        )

                    embeds.append(embed)

            if embeds:
                await interaction.followup.send(embeds=embeds[:3])  # Discord制限により最大3個まで
            else:
                await interaction.followup.send("📝 タグ提案可能なノートが見つかりません")

    async def _handle_tag_application(
        self,
        interaction: discord.Interaction,
        note_id: str,
        max_suggestions: int,
        confidence_threshold: float,
    ) -> None:
        """タグ自動適用モードの処理"""
        if not self.knowledge_manager:
            await interaction.followup.send("❌ KnowledgeManagerが利用できません", ephemeral=True)
            return

        if not note_id:
            await interaction.followup.send("❌ apply モードでは note_id の指定が必要です", ephemeral=True)
            return

        note = await self.knowledge_manager.get_note(note_id)
        if not note:
            await interaction.followup.send(f"❌ ノート '{note_id}' が見つかりません", ephemeral=True)
            return

        # タグ提案を取得
        suggestions = await self.knowledge_manager.suggest_tags_for_content(
            content=note["content"],
            title=note["title"],
            existing_tags=note.get("tags", []),
            max_suggestions=max_suggestions,
        )

        # 高信頼度タグを自動適用
        applied_tags = []
        for suggestion in suggestions:
            if suggestion["confidence"] >= confidence_threshold:
                applied_tags.append(suggestion["tag"])

        if applied_tags:
            # 既存タグと統合
            current_tags = set(note.get("tags", []))
            new_tags = list(current_tags.union(applied_tags))

            # ノート更新
            await self.knowledge_manager.update_note(note_id=note_id, tags=new_tags)

            embed = discord.Embed(
                title="✅ タグ自動適用完了", description=f"**ノート**: {note['title']}", color=0x00FF00
            )
            embed.add_field(
                name="適用されたタグ", value=", ".join([f"`{tag}`" for tag in applied_tags]), inline=False
            )
            embed.add_field(name="信頼度閾値", value=f"{confidence_threshold:.2f}", inline=True)
            embed.add_field(
                name="適用数/提案数", value=f"{len(applied_tags)}/{len(suggestions)}", inline=True
            )

            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="⚠️ 適用可能なタグなし",
                description=f"信頼度 {confidence_threshold:.2f} 以上のタグ提案がありませんでした",
                color=0xFFA500,
            )

            if suggestions:
                embed.add_field(
                    name="提案されたタグ（参考）",
                    value="\n".join(
                        [f"• {s['tag']} (信頼度: {s['confidence']:.2f})" for s in suggestions[:5]]
                    ),
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

    async def _handle_batch_tagging(
        self, interaction: discord.Interaction, max_suggestions: int, confidence_threshold: float
    ) -> None:
        """一括タグ付けモードの処理"""
        if not self.knowledge_manager:
            await interaction.followup.send("❌ KnowledgeManagerが利用できません", ephemeral=True)
            return

        # プログレス表示用のメッセージ
        progress_embed = discord.Embed(
            title="🔄 一括タグ付け実行中...",
            description="ノートを分析してタグを自動適用しています",
            color=0x0099FF,
        )
        # type: ignore[func-returns-value]
        progress_message = await interaction.followup.send(embed=progress_embed)
        # Note: Discord.py typing inconsistency - followup.send may return None

        # プログレスコールバック関数（同期関数として定義）
        def progress_callback(processed: int, total: int) -> None:
            """プログレス更新のコールバック（同期関数）"""
            if processed % 10 == 0 or processed == total:  # 10件ごと、または完了時に更新
                progress_embed.description = f"進捗: {processed}/{total} ノート処理完了"
                # 非同期更新は後で実行（create_task不要、直接実行はしない）

        # 一括カテゴリ化実行
        results = await self.knowledge_manager.auto_categorize_notes(
            batch_size=5, progress_callback=progress_callback  # 小さなバッチサイズでGemini API制限を考慮
        )

        # 結果を報告
        result_embed = discord.Embed(
            title="✅ 一括タグ付け完了",
            color=0x00FF00 if not results["errors"] else 0xFFA500,
        )

        result_embed.add_field(
            name="📊 処理結果",
            value=f"• 処理済み: {results['processed']} ノート\n"
            f"• タグ付け済み: {results['categorized']} ノート\n"
            f"• エラー: {len(results['errors'])} 件",
            inline=False,
        )

        if results["categorized"] > 0:
            # 適用されたタグのサンプルを表示
            sample_categories = list(results["categories"].items())[:3]
            sample_text = []
            for note_id, category_info in sample_categories:
                tags = ", ".join([f"`{tag}`" for tag in category_info["added_tags"]])
                sample_text.append(f"• {note_id[:8]}: {tags}")

            if sample_text:
                result_embed.add_field(
                    name="🏷️ 適用例（最大3件）", value="\n".join(sample_text), inline=False
                )

        if results["errors"]:
            result_embed.add_field(
                name="⚠️ エラー詳細",
                value="\n".join(results["errors"][:3])
                + ("..." if len(results["errors"]) > 3 else ""),
                inline=False,
            )

        result_embed.add_field(
            name="⚙️ 設定",
            value=f"信頼度閾値: {confidence_threshold:.2f}\n最大提案数: {max_suggestions}",
            inline=True,
        )

        # プログレスメッセージを最終結果で更新
        try:
            if progress_message:
                await progress_message.edit(embed=result_embed)
            else:
                await interaction.followup.send(embed=result_embed)
        except Exception:
            # Fallback: send as new message if edit fails
            await interaction.followup.send(embed=result_embed)

    async def _send_tag_suggestions_response(
        self,
        interaction: discord.Interaction,
        note: Dict[str, Any],
        suggestions: List[Dict[str, Any]],
    ) -> None:
        """タグ提案結果のレスポンス送信"""
        if not suggestions:
            embed = discord.Embed(
                title="📝 タグ提案",
                description=f"**ノート**: {note['title']}\n\n" "提案できるタグがありませんでした",
                color=0x999999,
            )
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(
            title="🏷️ AIタグ提案",
            description=f"**ノート**: {note['title'][:100]}"
            + ("..." if len(note["title"]) > 100 else ""),
            color=0x0099FF,
        )

        # 現在のタグを表示
        if note.get("tags"):
            embed.add_field(
                name="📌 現在のタグ", value=", ".join([f"`{tag}`" for tag in note["tags"]]), inline=False
            )

        # 提案タグを表示
        for i, suggestion in enumerate(suggestions):
            confidence_emoji = (
                "🟢"
                if suggestion["confidence"] >= 0.8
                else "🟡"
                if suggestion["confidence"] >= 0.6
                else "🔴"
            )
            embed.add_field(
                name=f"{confidence_emoji} {i+1}. {suggestion['tag']}",
                value=f"信頼度: {suggestion['confidence']:.2f}\n"
                + f"{suggestion['reason'][:150]}"
                + ("..." if len(suggestion["reason"]) > 150 else ""),
                inline=False,
            )

        embed.add_field(
            name="💡 使用方法", value="手動でタグを適用するか、`/auto-tag apply` で高信頼度タグを自動適用できます", inline=False
        )

        await interaction.followup.send(embed=embed)

    # Edit command
    @pkm_group.command(name="edit", description="既存のノートを編集します")
    @app_commands.describe(note_id="編集するノートID（省略時は検索で選択）", query="ノート検索クエリ（ファジー検索）")
    async def edit_command(
        self,
        interaction: discord.Interaction,
        note_id: Optional[str] = None,
        query: Optional[str] = None,
    ) -> None:
        """Edit an existing note with interactive selection."""
        if not await self._check_services(interaction):
            return

        await interaction.response.defer()
        user_id = str(interaction.user.id)

        try:
            target_note = None

            if note_id:
                # Direct note ID specified
                assert self.knowledge_manager is not None
                target_note = await self.knowledge_manager.get_note(note_id)

                if not target_note:
                    embed = PKMEmbed.error("ノートが見つかりません", f"ID `{note_id}` のノートは存在しません。")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                # Check ownership
                if target_note.get("user_id") != user_id:
                    embed = PKMEmbed.error("権限エラー", "他のユーザーのノートは編集できません。")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                # Show edit modal
                modal = EditNoteModal(target_note, self.knowledge_manager)
                await interaction.followup.send("編集フォームを表示します...", ephemeral=True)
                await interaction.edit_original_response(content="編集フォームを開いてください。")
                await modal.send_modal(interaction)

            elif query:
                # Search and select
                assert self.search_engine is not None
                filters = SearchFilters(user_id=user_id, min_score=0.3)

                search_results = await asyncio.wait_for(
                    self.search_engine.hybrid_search(
                        query=query, mode=SearchMode.HYBRID, limit=10, filters=filters
                    ),
                    timeout=COMMAND_TIMEOUT,
                )

                if not search_results:
                    embed = PKMEmbed.error("検索結果なし", "該当するノートが見つかりませんでした。検索クエリを変更してください。")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                # Show selection dropdown
                assert self.knowledge_manager is not None
                view = EditNoteSelectionView(search_results, self.knowledge_manager, user_id)
                embed = PKMEmbed.success(
                    "編集するノートを選択", f"検索結果: {len(search_results)}件\n下のドロップダウンから編集するノートを選択してください。"
                )
                await interaction.followup.send(embed=embed, view=view)

            else:
                # Show recent notes for selection
                assert self.knowledge_manager is not None
                recent_notes = await self.knowledge_manager.list_notes(
                    user_id=user_id, limit=10, offset=0
                )

                if not recent_notes:
                    embed = PKMEmbed.error("ノートがありません", "編集できるノートがありません。まずノートを作成してください。")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                # Show selection dropdown
                view = EditNoteSelectionView(
                    recent_notes, self.knowledge_manager, user_id, is_recent=True
                )
                embed = PKMEmbed.success(
                    "最近のノートから編集", f"最近のノート: {len(recent_notes)}件\n下のドロップダウンから編集するノートを選択してください。"
                )
                await interaction.followup.send(embed=embed, view=view)

        except asyncio.TimeoutError:
            embed = PKMEmbed.error("処理がタイムアウトしました", "検索処理に時間がかかりすぎました。")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in edit command: {e}")
            embed = PKMEmbed.error("エラーが発生しました", "ノート編集処理中にエラーが発生しました。")
            await interaction.followup.send(embed=embed, ephemeral=True)


class NoteMergeView(discord.ui.View):
    """Interactive view for note merging with AI suggestions."""

    def __init__(
        self,
        selected_notes: List[Dict[str, Any]],
        knowledge_manager: KnowledgeManager,
        custom_title: Optional[str] = None,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        timeout: float = 300.0,
    ):
        super().__init__(timeout=timeout)
        self.selected_notes = selected_notes
        self.knowledge_manager = knowledge_manager
        self.custom_title = custom_title
        self.user_id = user_id
        self.guild_id = guild_id
        self.suggested_notes: List[Dict[str, Any]] = []
        self.final_notes = selected_notes.copy()
        self._suggestions_loaded = False

    def create_initial_embed(self) -> discord.Embed:
        """Create initial embed showing selected notes."""
        embed = discord.Embed(
            title="📝 ノート統合 - Phase 1: 初期選択", color=0x2ECC71, timestamp=datetime.utcnow()
        )

        selected_text = "\n".join(
            [f"• **{note['title']}** ({len(note['content'])} 文字)" for note in self.selected_notes]
        )

        embed.add_field(name="🎯 選択されたノート", value=selected_text, inline=False)

        embed.add_field(name="⏳ 次のステップ", value="AI が関連するノートを分析中...", inline=False)

        embed.set_footer(text="関連ノート提案は30秒でタイムアウトします")
        return embed

    async def load_suggestions(self) -> None:
        """Load AI-powered note suggestions with enhanced semantic analysis."""
        if self._suggestions_loaded:
            return

        try:
            # Combine content from selected notes for analysis
            combined_content = " ".join([note["content"] for note in self.selected_notes])
            combined_tags = []
            selected_titles = []
            for note in self.selected_notes:
                combined_tags.extend(note.get("tags", []))
                selected_titles.append(note["title"])

            # Multi-phase search for comprehensive coverage
            all_candidate_notes = set()

            # Phase 1: Content-based semantic search
            content_query = (
                combined_content[:500] if len(combined_content) > 500 else combined_content
            )
            if content_query.strip():
                semantic_notes = await self.knowledge_manager.search_notes(
                    query=content_query, limit=15
                )
                for note in semantic_notes:
                    all_candidate_notes.add(note["id"])

            # Phase 2: Title-based keyword search for related concepts
            title_keywords = " ".join(selected_titles)
            if title_keywords.strip():
                keyword_notes = await self.knowledge_manager.search_notes(
                    query=title_keywords, limit=10
                )
                for note in keyword_notes:
                    all_candidate_notes.add(note["id"])

            # Phase 3: Tag-based discovery for broader context
            unique_tags = list(set(combined_tags))[:3]  # Top 3 unique tags
            for tag in unique_tags:
                if tag:
                    tag_notes = await self.knowledge_manager.get_notes_by_tag(tag, limit=5)
                    for note in tag_notes:
                        all_candidate_notes.add(note["id"])

            # Remove already selected notes
            selected_ids = {note["id"] for note in self.selected_notes}
            candidate_ids = all_candidate_notes - selected_ids

            # Get full note data for scoring
            candidates: List[Dict[str, Any]] = []
            for note_id in candidate_ids:
                retrieved_note = await self.knowledge_manager.get_note(note_id)
                if retrieved_note is not None:
                    candidates.append(retrieved_note)

            # Enhanced relevance scoring with multiple factors
            scored_candidates = []
            for note in candidates:
                score = self._calculate_enhanced_relevance_score(
                    note, combined_content, combined_tags, selected_titles
                )

                if score > 50:  # Minimum threshold for relevance
                    scored_candidates.append(
                        {"note": note, "relevance": min(95, max(50, int(score)))}  # 50-95% range
                    )

            # Sort by relevance and add diversity
            scored_candidates.sort(
                key=lambda x: int(x["relevance"])
                if isinstance(x["relevance"], (int, float))
                else 0,
                reverse=True,
            )

            # Apply diversity filtering to prevent echo chamber
            self.suggested_notes = self._apply_diversity_filter(scored_candidates[:8])[:5]
            self._suggestions_loaded = True

        except Exception as e:
            logger.error(f"Failed to load note suggestions: {e}")
            self.suggested_notes = []
            self._suggestions_loaded = True

    def _calculate_enhanced_relevance_score(
        self,
        candidate_note: Dict[str, Any],
        combined_content: str,
        combined_tags: List[str],
        selected_titles: List[str],
    ) -> float:
        """Calculate enhanced relevance score using multiple factors."""
        score = 0.0

        # Factor 1: Tag overlap (25% weight)
        note_tags = candidate_note.get("tags", [])
        tag_overlap = len(set(note_tags) & set(combined_tags))
        if combined_tags:
            tag_score = (tag_overlap / len(set(combined_tags))) * 25
            score += tag_score

        # Factor 2: Content length similarity (15% weight)
        candidate_length = len(candidate_note["content"])
        avg_selected_length = len(combined_content) / len(self.selected_notes)

        length_ratio = min(candidate_length, avg_selected_length) / max(
            candidate_length, avg_selected_length, 1
        )
        length_score = length_ratio * 15
        score += length_score

        # Factor 3: Title keyword intersection (20% weight)
        candidate_title = candidate_note["title"].lower()
        title_keywords = " ".join(selected_titles).lower().split()
        title_matches = sum(1 for word in title_keywords if word in candidate_title)
        if title_keywords:
            title_score = (title_matches / len(title_keywords)) * 20
            score += title_score

        # Factor 4: Content keyword density (25% weight)
        content_words = set(combined_content.lower().split())
        candidate_words = set(candidate_note["content"].lower().split())

        if content_words and candidate_words:
            intersection = len(content_words & candidate_words)
            union = len(content_words | candidate_words)
            jaccard_similarity = intersection / union if union > 0 else 0
            content_score = jaccard_similarity * 25
            score += content_score

        # Factor 5: Temporal proximity bonus (10% weight)
        try:
            from datetime import datetime, timezone

            # Get newest selected note timestamp
            newest_selected = max(
                datetime.fromisoformat(note.get("created_at", "1970-01-01")).replace(
                    tzinfo=timezone.utc
                )
                for note in self.selected_notes
                if note.get("created_at")
            )

            candidate_time = datetime.fromisoformat(
                candidate_note.get("created_at", "1970-01-01")
            ).replace(tzinfo=timezone.utc)

            time_diff_days = abs((newest_selected - candidate_time).days)

            # Bonus for notes created within 30 days
            if time_diff_days <= 30:
                temporal_bonus = (30 - time_diff_days) / 30 * 10
                score += temporal_bonus

        except (ValueError, TypeError):
            # Skip temporal scoring if date parsing fails
            pass

        # Factor 6: Source type diversity bonus (5% weight)
        selected_types = {note.get("source_type", "manual") for note in self.selected_notes}
        candidate_type = candidate_note.get("source_type", "manual")

        if candidate_type not in selected_types:
            score += 5  # Diversity bonus

        return score

    def _apply_diversity_filter(
        self, scored_candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply diversity filtering to prevent similar suggestions."""
        if len(scored_candidates) <= 3:
            return scored_candidates

        filtered: List[Dict[str, Any]] = []
        used_tag_combinations = set()

        for candidate in scored_candidates:
            note = candidate["note"]
            note_tags = tuple(sorted(note.get("tags", [])))

            # Ensure tag diversity
            if len(filtered) < 2:
                # Always include top 2 candidates
                filtered.append(candidate)
                used_tag_combinations.add(note_tags)
            elif note_tags not in used_tag_combinations or len(filtered) >= 5:
                # Add diverse candidates or fill remaining slots
                filtered.append(candidate)
                used_tag_combinations.add(note_tags)

            if len(filtered) >= 5:
                break

        return filtered

    async def update_embed_with_suggestions(self, interaction: discord.Interaction) -> None:
        """Update embed to show AI suggestions."""
        await self.load_suggestions()

        embed = discord.Embed(
            title="📝 ノート統合 - Phase 2: AI提案", color=0x3498DB, timestamp=datetime.utcnow()
        )

        # Selected notes
        selected_text = "\n".join([f"• **{note['title']}**" for note in self.selected_notes])
        embed.add_field(name="✅ 選択済みノート", value=selected_text, inline=False)

        # AI suggestions
        if self.suggested_notes:
            suggestions_text = "\n".join(
                [
                    f"• **{item['note']['title']}** - 関連度: {item['relevance']}%"
                    for item in self.suggested_notes[:3]  # Show top 3
                ]
            )
            embed.add_field(name="🤖 AI提案 (関連する可能性のあるノート)", value=suggestions_text, inline=False)
        else:
            embed.add_field(name="🤖 AI提案", value="関連するノートが見つかりませんでした。", inline=False)

        embed.add_field(name="📋 次のアクション", value="提案を確認し、統合対象を選択してください。", inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔍 関連ノート提案を表示", style=discord.ButtonStyle.primary)
    async def show_suggestions(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Show AI-powered note suggestions."""
        button.disabled = True
        await self.update_embed_with_suggestions(interaction)

    @discord.ui.button(label="➕ 全て追加", style=discord.ButtonStyle.secondary)
    async def add_all_suggestions(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Add all suggested notes to merge."""
        await self.load_suggestions()

        for item in self.suggested_notes:
            self.final_notes.append(item["note"])

        await self.show_final_confirmation(interaction)

    @discord.ui.button(label="🔧 個別選択", style=discord.ButtonStyle.secondary)
    async def individual_selection(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Show individual note selection interface."""
        await self.load_suggestions()

        if not self.suggested_notes:
            await interaction.response.send_message("❌ 提案するノートがありません。", ephemeral=True)
            return

        # Create selection dropdown
        options = []
        for i, item in enumerate(self.suggested_notes[:5]):  # Max 5 options
            note = item["note"]
            options.append(
                discord.SelectOption(
                    label=note["title"][:100],  # Discord limit
                    description=f"関連度: {item['relevance']}% | {len(note['content'])} 文字",
                    value=str(i),
                )
            )

        select = NoteSelectionDropdown(options, self)
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("📋 追加するノートを選択してください:", view=view, ephemeral=True)

    @discord.ui.button(label="⏭️ スキップして統合", style=discord.ButtonStyle.success)
    async def skip_to_merge(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Skip suggestions and proceed with merge."""
        await self.show_final_confirmation(interaction)

    async def show_final_confirmation(self, interaction: discord.Interaction) -> None:
        """Show final confirmation before merge."""
        embed = discord.Embed(
            title="📝 ノート統合 - Phase 3: 最終確認", color=0xE74C3C, timestamp=datetime.utcnow()
        )

        notes_text = "\n".join(
            [f"• **{note['title']}** ({len(note['content'])} 文字)" for note in self.final_notes]
        )

        embed.add_field(
            name=f"📄 統合対象ノート ({len(self.final_notes)}個)", value=notes_text, inline=False
        )

        total_chars = sum(len(note["content"]) for note in self.final_notes)
        embed.add_field(
            name="📊 統合予測", value=f"• 総文字数: {total_chars} 文字\n• 予想圧縮率: ~30-40%", inline=False
        )

        # Clear previous buttons and add final action buttons
        self.clear_items()
        self.add_item(ExecuteMergeButton())
        self.add_item(CancelMergeButton())

        await interaction.response.edit_message(embed=embed, view=self)


class NoteSelectionDropdown(discord.ui.Select):
    """Dropdown for individual note selection."""

    def __init__(self, options: List[discord.SelectOption], parent_view: NoteMergeView):
        super().__init__(placeholder="追加するノートを選択...", options=options, max_values=len(options))
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle note selection."""
        selected_indices = [int(str(value)) for value in self.values]

        for index in selected_indices:
            note = self.parent_view.suggested_notes[index]["note"]
            if note not in self.parent_view.final_notes:
                self.parent_view.final_notes.append(note)

        await interaction.response.send_message(
            f"✅ {len(selected_indices)} 個のノートを追加しました。元の画面で統合を続行してください。", ephemeral=True
        )


class ExecuteMergeButton(discord.ui.Button):
    """Button to execute the merge operation."""

    def __init__(self):
        super().__init__(label="🚀 統合実行", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Execute note merge."""
        view = self.view
        assert isinstance(view, NoteMergeView)
        await interaction.response.defer()

        try:
            # Show processing status
            processing_embed = discord.Embed(
                title="⏳ ノート統合処理中...",
                description="AI がノートを分析・統合しています。しばらくお待ちください...",
                color=0xF39C12,
                timestamp=datetime.utcnow(),
            )

            processing_steps = [
                "🔄 内容分析中... (1/4)",
                "🔄 構造化中... (2/4)",
                "🔄 統合文書生成中... (3/4)",
                "🔄 メタデータ更新中... (4/4)",
            ]

            for step in processing_steps:
                processing_embed.description = step
                await interaction.edit_original_response(embed=processing_embed)
                await asyncio.sleep(1)  # Simulate processing time

            # Execute merge using knowledge manager
            note_ids = [note["id"] for note in view.final_notes]
            merged_title = view.custom_title or f"統合ノート_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            merged_note_id = await view.knowledge_manager.merge_notes(
                note_ids=note_ids, new_title=merged_title
            )

            # Get the merged note for display
            merged_note = await view.knowledge_manager.get_note(merged_note_id)

            # Show success result
            success_embed = discord.Embed(
                title="✨ ノート統合完了!", color=0x27AE60, timestamp=datetime.utcnow()
            )

            if merged_note is not None:
                success_embed.add_field(
                    name="📄 新規統合ノート", value=f"**{merged_note['title']}**", inline=False
                )

                original_chars = sum(len(note["content"]) for note in view.final_notes)
                merged_chars = len(merged_note["content"])
                compression_rate = int((1 - merged_chars / original_chars) * 100)

                success_embed.add_field(
                    name="📊 統合サマリー",
                    value=f"• 統合ノート数: {len(view.final_notes)}個\n"
                    f"• 文字数: {original_chars} → {merged_chars} ({compression_rate}%圧縮)",
                    inline=False,
                )
            else:
                success_embed.add_field(
                    name="⚠️ 注意",
                    value="統合は完了しましたが、結果の表示に問題が発生しました。",
                    inline=False,
                )

            # Clear buttons
            view.clear_items()

            await interaction.edit_original_response(embed=success_embed, view=view)

        except Exception as e:
            logger.error(f"Merge execution failed: {e}")

            error_embed = discord.Embed(
                title="❌ 統合失敗", description=f"ノート統合中にエラーが発生しました: {e}", color=0xE74C3C
            )

            await interaction.edit_original_response(embed=error_embed, view=None)


class CancelMergeButton(discord.ui.Button):
    """Button to cancel the merge operation."""

    def __init__(self):
        super().__init__(label="❌ キャンセル", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Cancel merge operation."""
        embed = discord.Embed(
            title="❌ 統合をキャンセルしました", description="ノート統合操作がキャンセルされました。", color=0x95A5A6
        )

        view = self.view
        assert isinstance(view, NoteMergeView)
        view.clear_items()
        await interaction.response.edit_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(PKMCog(bot))
    logger.info("PKMCog loaded successfully")
