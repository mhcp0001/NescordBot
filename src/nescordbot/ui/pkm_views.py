"""Discord UI components for PKM functionality."""

import logging
from typing import Any, Callable, Dict, List, Optional

import discord

from ..services.knowledge_manager import KnowledgeManager
from ..services.search_engine import SearchResult
from .pkm_embeds import PKMEmbed

logger = logging.getLogger(__name__)


class PKMNoteView(discord.ui.View):
    """Interactive view for note operations."""

    def __init__(
        self, note_data: Dict[str, Any], knowledge_manager: KnowledgeManager, user_id: str
    ):
        super().__init__(timeout=300)
        self.note_data = note_data
        self.km = knowledge_manager
        self.user_id = user_id

    @discord.ui.button(label="編集", style=discord.ButtonStyle.primary, emoji="📝")
    async def edit_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit note (placeholder for future implementation)."""
        embed = PKMEmbed.info("編集機能", "ノート編集機能は今後のアップデートで実装予定です。\n現在は新しいノートを作成してください。")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="削除", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete note with confirmation."""
        await interaction.response.send_modal(
            DeleteConfirmationModal(
                note_data=self.note_data, knowledge_manager=self.km, user_id=self.user_id
            )
        )

    @discord.ui.button(label="GitHubに保存", style=discord.ButtonStyle.success, emoji="💾")
    async def save_to_github(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save note to GitHub via ObsidianGitHubService."""
        embed = PKMEmbed.info("GitHub保存機能", "GitHub連携機能は今後のアップデートで実装予定です。\n現在はローカルDBに保存されています。")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="関連ノート", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def find_related(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Find related notes."""
        embed = PKMEmbed.info("関連ノート機能", "関連ノート検索機能は今後のアップデートで実装予定です。\n手動で検索コマンドをお使いください。")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SearchResultView(discord.ui.View):
    """Paginated view for search results."""

    def __init__(
        self,
        search_results: List[SearchResult],
        query: str,
        knowledge_manager: KnowledgeManager,
        user_id: str,
        page: int = 0,
    ):
        super().__init__(timeout=300)
        self.results = search_results
        self.query = query
        self.km = knowledge_manager
        self.user_id = user_id
        self.current_page = page
        self.page_size = 3
        self.total_pages = max(1, (len(search_results) + self.page_size - 1) // self.page_size)

        # ページネーションボタンの状態更新
        self.update_button_states()

    def update_button_states(self):
        """Update button states based on current page."""
        self.previous_page.disabled = self.current_page <= 0
        self.next_page.disabled = self.current_page >= self.total_pages - 1

    @discord.ui.button(label="前へ", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_button_states()

            embed = PKMEmbed.search_results(
                results=self.get_current_page_results(),
                query=self.query,
                page=self.current_page,
                total_pages=self.total_pages,
                total_results=len(self.results),
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_button_states()

            embed = PKMEmbed.search_results(
                results=self.get_current_page_results(),
                query=self.query,
                page=self.current_page,
                total_pages=self.total_pages,
                total_results=len(self.results),
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="詳細表示", style=discord.ButtonStyle.primary, emoji="🔍")
    async def view_detail(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show detailed note view for selected result."""
        await interaction.response.send_modal(
            NoteSelectionModal(
                results=self.get_current_page_results(),
                knowledge_manager=self.km,
                user_id=self.user_id,
                callback_type="detail",
            )
        )

    def get_current_page_results(self) -> List[SearchResult]:
        """Get results for current page."""
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.results[start:end]


class PKMListView(discord.ui.View):
    """Paginated view for note lists."""

    def __init__(
        self,
        notes: List[Dict[str, Any]],
        sort_by: str,
        filter_type: str,
        knowledge_manager: KnowledgeManager,
        user_id: str,
        page: int = 0,
    ):
        super().__init__(timeout=300)
        self.notes = notes
        self.sort_by = sort_by
        self.filter_type = filter_type
        self.km = knowledge_manager
        self.user_id = user_id
        self.current_page = page
        self.page_size = 5
        self.total_pages = max(1, (len(notes) + self.page_size - 1) // self.page_size)

        # ページネーションボタンの状態更新
        self.update_button_states()

    def update_button_states(self):
        """Update button states based on current page."""
        self.previous_page.disabled = self.current_page <= 0
        self.next_page.disabled = self.current_page >= self.total_pages - 1

    @discord.ui.button(label="前へ", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_button_states()

            embed = PKMEmbed.note_list(
                notes=self.get_current_page_notes(),
                page=self.current_page,
                total_pages=self.total_pages,
                total_notes=len(self.notes),
                sort_by=self.sort_by,
                filter_type=self.filter_type,
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_button_states()

            embed = PKMEmbed.note_list(
                notes=self.get_current_page_notes(),
                page=self.current_page,
                total_pages=self.total_pages,
                total_notes=len(self.notes),
                sort_by=self.sort_by,
                filter_type=self.filter_type,
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="詳細表示", style=discord.ButtonStyle.primary, emoji="📄")
    async def view_detail(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show detailed note view for selected note."""
        await interaction.response.send_modal(
            NoteSelectionModal(
                notes=self.get_current_page_notes(),
                knowledge_manager=self.km,
                user_id=self.user_id,
                callback_type="detail",
            )
        )

    def get_current_page_notes(self) -> List[Dict[str, Any]]:
        """Get notes for current page."""
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.notes[start:end]


class DeleteConfirmationModal(discord.ui.Modal):
    """Modal for note deletion confirmation."""

    def __init__(
        self, note_data: Dict[str, Any], knowledge_manager: KnowledgeManager, user_id: str
    ):
        super().__init__(title="ノート削除の確認")
        self.note_data = note_data
        self.km = knowledge_manager
        self.user_id = user_id

        self.confirmation: discord.ui.TextInput = discord.ui.TextInput(
            label="削除するには「削除」と入力してください", placeholder="削除", required=True, max_length=10
        )
        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle deletion confirmation."""
        if self.confirmation.value.strip() == "削除":
            try:
                success = await self.km.delete_note(self.note_data["id"])
                if success:
                    embed = PKMEmbed.success(
                        "削除完了", f"ノート「{self.note_data.get('title', 'タイトルなし')}」を削除しました。"
                    )
                else:
                    embed = PKMEmbed.error("削除に失敗しました", "ノートが見つからないか、削除権限がありません。")
            except Exception as e:
                logger.error(f"Error deleting note: {e}")
                embed = PKMEmbed.error("削除エラー", "ノートの削除中にエラーが発生しました。")
        else:
            embed = PKMEmbed.error("削除がキャンセルされました", "正確に「削除」と入力してください。")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class NoteSelectionModal(discord.ui.Modal):
    """Modal for selecting a note from list for detail view."""

    def __init__(
        self,
        notes: Optional[List[Dict[str, Any]]] = None,
        results: Optional[List[SearchResult]] = None,
        knowledge_manager: Optional[KnowledgeManager] = None,
        user_id: str = "",
        callback_type: str = "detail",
    ):
        super().__init__(title="ノート選択")
        self.notes = notes or []
        self.results = results or []
        self.km = knowledge_manager
        self.user_id = user_id
        self.callback_type = callback_type

        # 選択用入力フィールド
        max_num = len(self.notes) if self.notes else len(self.results)
        self.selection: discord.ui.TextInput = discord.ui.TextInput(
            label=f"番号を入力（1-{max_num}）", placeholder="1", required=True, max_length=2
        )
        self.add_item(self.selection)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle note selection."""
        try:
            selection_num = int(self.selection.value.strip())

            if self.notes:
                if 1 <= selection_num <= len(self.notes):
                    note = self.notes[selection_num - 1]
                    embed = PKMEmbed.note_detail(note)
                    if self.km is None:
                        await interaction.response.send_message("サービスが初期化されていません", ephemeral=True)
                        return
                    view = PKMNoteView(note, self.km, self.user_id)
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                else:
                    raise ValueError(f"Invalid selection: {selection_num}")

            elif self.results:
                if 1 <= selection_num <= len(self.results):
                    result = self.results[selection_num - 1]
                    # SearchResultからノート詳細を取得
                    if self.km is None:
                        await interaction.response.send_message("サービスが初期化されていません", ephemeral=True)
                        return
                    note = await self.km.get_note(result.note_id)
                    if note is not None:
                        embed = PKMEmbed.note_detail(note)
                        view = PKMNoteView(note, self.km, self.user_id)
                        await interaction.response.send_message(
                            embed=embed, view=view, ephemeral=True
                        )
                    else:
                        embed = PKMEmbed.error("ノートが見つかりません", "ノートが削除されている可能性があります。")
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    raise ValueError(f"Invalid selection: {selection_num}")

        except ValueError:
            embed = PKMEmbed.error(
                "無効な選択", f"1から{len(self.notes) if self.notes else len(self.results)}の間の数字を入力してください。"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in note selection: {e}")
            embed = PKMEmbed.error("エラーが発生しました", "ノートの表示中にエラーが発生しました。")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class PKMPaginationView(discord.ui.View):
    """Base class for paginated views."""

    def __init__(self, total_items: int, page_size: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.total_items = total_items
        self.page_size = page_size
        self.current_page = 0
        self.total_pages = max(1, (total_items + page_size - 1) // page_size)

    def update_button_states(self):
        """Update pagination button states."""
        if hasattr(self, "previous_button"):
            self.previous_button.disabled = self.current_page <= 0
        if hasattr(self, "next_button"):
            self.next_button.disabled = self.current_page >= self.total_pages - 1

    async def update_page(self, interaction: discord.Interaction, new_page: int):
        """Update to new page - override in subclasses."""
        pass


class SearchFilterView(discord.ui.View):
    """View for search filter options."""

    def __init__(self, callback: Callable):
        super().__init__(timeout=300)
        self.callback = callback

    @discord.ui.select(
        placeholder="ノートタイプでフィルタ",
        options=[
            discord.SelectOption(label="全て", value="all", emoji="📚"),
            discord.SelectOption(label="永続ノート", value="permanent", emoji="📖"),
            discord.SelectOption(label="一時ノート", value="fleeting", emoji="📝"),
            discord.SelectOption(label="リンク", value="link", emoji="🔗"),
        ],
    )
    async def select_type_filter(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle type filter selection."""
        await self.callback(interaction, "type", select.values[0])

    @discord.ui.select(
        placeholder="ソート順を選択",
        options=[
            discord.SelectOption(label="更新日時（新しい順）", value="updated_desc", emoji="🕒"),
            discord.SelectOption(label="作成日時（新しい順）", value="created_desc", emoji="📅"),
            discord.SelectOption(label="タイトル（昇順）", value="title_asc", emoji="🔤"),
            discord.SelectOption(label="スコア（高い順）", value="score_desc", emoji="⭐"),
        ],
    )
    async def select_sort_order(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle sort order selection."""
        await self.callback(interaction, "sort", select.values[0])


class PKMHelpView(discord.ui.View):
    """Help view with quick command references."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="コマンド一覧", style=discord.ButtonStyle.primary, emoji="📋")
    async def show_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show available PKM commands."""
        embed = discord.Embed(
            title="📋 PKMコマンド一覧",
            description="Personal Knowledge Management機能のコマンド一覧",
            color=PKMEmbed.COLOR_INFO,
        )

        embed.add_field(
            name="/pkm note", value="新しいノートを作成します\n`title` `content` `tags` `type`", inline=False
        )
        embed.add_field(
            name="/pkm search", value="ノートを検索します\n`query` `limit` `type` `min_score`", inline=False
        )
        embed.add_field(
            name="/pkm list", value="ノート一覧を表示します\n`limit` `sort` `type` `tag`", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="使用例", style=discord.ButtonStyle.secondary, emoji="💡")
    async def show_examples(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show usage examples."""
        embed = discord.Embed(title="💡 使用例", description="PKM機能の使用例", color=PKMEmbed.COLOR_INFO)

        embed.add_field(
            name="ノート作成例",
            value='`/pkm note title:"会議メモ" content:"今日の会議で決まったこと" tags:"会議,重要"`',
            inline=False,
        )
        embed.add_field(
            name="検索例", value='`/pkm search query:"Python プログラミング" limit:10`', inline=False
        )
        embed.add_field(
            name="一覧表示例", value="`/pkm list sort:updated type:permanent limit:20`", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
