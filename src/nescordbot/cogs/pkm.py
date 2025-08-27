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


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(PKMCog(bot))
    logger.info("PKMCog loaded successfully")
