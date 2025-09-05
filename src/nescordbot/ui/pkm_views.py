"""Discord UI components for PKM functionality."""

import logging
from typing import Any, Callable, Dict, List, Optional

import discord
from typing_extensions import Self

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
                    retrieved_note = await self.km.get_note(result.note_id)
                    if retrieved_note is not None:
                        embed = PKMEmbed.note_detail(retrieved_note)
                        view = PKMNoteView(retrieved_note, self.km, self.user_id)
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


class EditNoteModal(discord.ui.Modal):
    """Modal for editing existing notes."""

    def __init__(self, note_data: Dict[str, Any], knowledge_manager: "KnowledgeManager"):
        super().__init__(title="ノートを編集")
        self.note_data = note_data
        self.km = knowledge_manager

        # Title input
        self.title_input: discord.ui.TextInput[Self] = discord.ui.TextInput(
            label="タイトル",
            default=note_data.get("title", ""),
            max_length=100,
            required=True,
        )
        self.add_item(self.title_input)

        # Content input
        content = note_data.get("content", "")
        self.content_input: discord.ui.TextInput[Self] = discord.ui.TextInput(
            label="内容",
            style=discord.TextStyle.paragraph,
            default=content,
            max_length=4000,
            required=True,
        )
        self.add_item(self.content_input)

        # Tags input
        tags = note_data.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        self.tags_input: discord.ui.TextInput[Self] = discord.ui.TextInput(
            label="タグ（カンマ区切り）",
            default=tags_str,
            max_length=200,
            required=False,
        )
        self.add_item(self.tags_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer()

        try:
            # Parse tags
            tags_list = []
            if self.tags_input.value.strip():
                tags_list = [tag.strip() for tag in self.tags_input.value.split(",") if tag.strip()]

            # Update note with user ID for history tracking
            success = await self.km.update_note(
                note_id=self.note_data["id"],
                title=self.title_input.value,
                content=self.content_input.value,
                tags=tags_list,
                user_id=str(interaction.user.id),
            )

            if success:
                embed = PKMEmbed.success("ノートを更新しました", f"ID: {self.note_data['id']}")
                embed.add_field(name="新しいタイトル", value=self.title_input.value, inline=False)
                if tags_list:
                    embed.add_field(name="タグ", value=", ".join(tags_list), inline=False)

                # Add view with history button
                view = EditNoteResultView(self.note_data["id"], self.km)
                await interaction.followup.send(embed=embed, view=view)
                logger.info(f"Note updated: {self.note_data['id']} by user {interaction.user.id}")
            else:
                embed = PKMEmbed.error("更新に失敗しました", "ノートの更新中にエラーが発生しました。")
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error updating note: {e}")
            embed = PKMEmbed.error("エラーが発生しました", "ノートの更新中にエラーが発生しました。")
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def send_modal(self, interaction: discord.Interaction):
        """Send the modal to the user."""
        await interaction.response.send_modal(self)


class EditNoteSelectionView(discord.ui.View):
    """View for selecting notes to edit."""

    def __init__(
        self,
        notes: List[Any],
        knowledge_manager: "KnowledgeManager",
        user_id: str,
        is_recent: bool = False,
    ):
        super().__init__(timeout=300)
        self.notes = notes
        self.km = knowledge_manager
        self.user_id = user_id
        self.is_recent = is_recent

        # Create dropdown
        options = []
        for i, note in enumerate(notes[:25]):  # Discord limit
            if self.is_recent:
                # For list_notes result format
                title = note.get("title", "無題")[:50]
                note_id = note.get("id", "")
                content_preview = note.get("content", "")[:50]
            else:
                # For search results format
                title = note.title[:50] if hasattr(note, "title") else "無題"
                note_id = note.id if hasattr(note, "id") else ""
                content_preview = note.content[:50] if hasattr(note, "content") else ""

            description = f"ID: {note_id} | {content_preview}..."

            options.append(
                discord.SelectOption(
                    label=title, description=description[:100], value=str(i)  # Discord limit
                )
            )

        self.note_select: discord.ui.Select[Self] = discord.ui.Select(
            placeholder="編集するノートを選択してください", options=options, row=0
        )
        self.note_select.callback = self.select_note  # type: ignore
        self.add_item(self.note_select)

    async def select_note(self, interaction: discord.Interaction):
        """Handle note selection."""
        try:
            selected_idx = int(self.note_select.values[0])
            selected_note = self.notes[selected_idx]

            # Convert to standard format if needed
            if self.is_recent:
                note_data = selected_note
            else:
                # Convert SearchResult to dict format
                note_data = {
                    "id": selected_note.id if hasattr(selected_note, "id") else "",
                    "title": selected_note.title if hasattr(selected_note, "title") else "",
                    "content": selected_note.content if hasattr(selected_note, "content") else "",
                    "tags": selected_note.tags if hasattr(selected_note, "tags") else [],
                    "user_id": self.user_id,
                }

            # Check ownership
            if note_data.get("user_id") != self.user_id:
                embed = PKMEmbed.error("権限エラー", "他のユーザーのノートは編集できません。")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Show edit modal
            modal = EditNoteModal(note_data, self.km)
            await modal.send_modal(interaction)

        except (ValueError, IndexError) as e:
            logger.error(f"Error in note selection: {e}")
            embed = PKMEmbed.error("選択エラー", "ノートの選択中にエラーが発生しました。")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EditNoteResultView(discord.ui.View):
    """View displayed after successful note edit with history button."""

    def __init__(self, note_id: str, knowledge_manager: "KnowledgeManager"):
        super().__init__(timeout=300)
        self.note_id = note_id
        self.km = knowledge_manager

    @discord.ui.button(label="編集履歴を表示", style=discord.ButtonStyle.secondary, emoji="📜")
    async def show_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show note edit history."""
        await interaction.response.defer()

        try:
            history = await self.km.get_note_history(self.note_id, limit=10)

            if not history:
                embed = PKMEmbed.info("編集履歴なし", "このノートに編集履歴がありません。")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Create history view
            view = NoteHistoryView(self.note_id, history, self.km)
            embed = await self._create_history_embed(history[0] if history else None)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting note history: {e}")
            embed = PKMEmbed.error("エラー", "履歴の取得中にエラーが発生しました。")
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def _create_history_embed(
        self, history_item: Optional[Dict[str, Any]] = None
    ) -> discord.Embed:
        """Create embed for history display."""
        if not history_item:
            return PKMEmbed.info("編集履歴", "履歴がありません。")

        embed = discord.Embed(
            title="📜 ノート編集履歴",
            description=f"ノートID: `{self.note_id}`",
            color=discord.Color.blue(),
        )

        # Add latest edit info
        embed.add_field(
            name="最新の編集",
            value=f"<@{history_item['user_id']}> - {history_item['timestamp']}",
            inline=False,
        )

        # Add changes summary
        changes = history_item.get("changes", {})
        if changes:
            change_summary = []
            if "title" in changes:
                change_summary.append("🏷️ タイトル変更")
            if "content" in changes:
                change_summary.append("📝 内容変更")
            if "tags" in changes:
                change_summary.append("🏷️ タグ変更")

            embed.add_field(
                name="変更内容",
                value="\n".join(change_summary) if change_summary else "変更なし",
                inline=False,
            )

        return embed


class NoteHistoryView(discord.ui.View):
    """View for navigating through note history."""

    def __init__(
        self, note_id: str, history: List[Dict[str, Any]], knowledge_manager: "KnowledgeManager"
    ):
        super().__init__(timeout=300)
        self.note_id = note_id
        self.history = history
        self.km = knowledge_manager
        self.current_index = 0

        # Update button states
        self._update_buttons()

    def _update_buttons(self):
        """Update button enabled states based on current position."""
        self.prev_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index >= len(self.history) - 1

    @discord.ui.button(label="◀️ 前の編集", style=discord.ButtonStyle.secondary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show previous edit in history."""
        if self.current_index > 0:
            self.current_index -= 1
            self._update_buttons()
            embed = await self._create_history_detail_embed(self.history[self.current_index])
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="次の編集 ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show next edit in history."""
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            self._update_buttons()
            embed = await self._create_history_detail_embed(self.history[self.current_index])
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="差分表示", style=discord.ButtonStyle.primary, emoji="🔍")
    async def show_diff(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show detailed diff for current history item."""
        history_item = self.history[self.current_index]
        modal = NoteDiffModal(history_item)
        await interaction.response.send_modal(modal)

    async def _create_history_detail_embed(self, history_item: Dict[str, Any]) -> discord.Embed:
        """Create detailed embed for a specific history item."""
        embed = discord.Embed(
            title=f"📜 編集履歴 ({self.current_index + 1}/{len(self.history)})",
            description=f"ノートID: `{self.note_id}`",
            color=discord.Color.blue(),
        )

        # Add edit info
        embed.add_field(
            name="編集者・日時",
            value=f"<@{history_item['user_id']}>\n{history_item['timestamp']}",
            inline=True,
        )

        embed.add_field(
            name="編集タイプ",
            value=history_item["edit_type"],
            inline=True,
        )

        # Add changes details
        changes = history_item.get("changes", {})

        if "title" in changes:
            title_change = changes["title"]
            embed.add_field(
                name="🏷️ タイトル変更",
                value=f"**変更前:** {title_change['before']}\n**変更後:** {title_change['after']}",
                inline=False,
            )

        if "content" in changes:
            content_change = changes["content"]
            embed.add_field(
                name="📝 内容変更",
                value=f"**変更前:** {content_change['before_lines']}行\n"
                f"**変更後:** {content_change['after_lines']}行",
                inline=True,
            )

        if "tags" in changes:
            tags_change = changes["tags"]
            added = ", ".join(tags_change["added"]) if tags_change["added"] else "なし"
            removed = ", ".join(tags_change["removed"]) if tags_change["removed"] else "なし"

            embed.add_field(
                name="🏷️ タグ変更",
                value=f"**追加:** {added}\n**削除:** {removed}",
                inline=False,
            )

        return embed


class NoteDiffModal(discord.ui.Modal):
    """Modal for displaying detailed diff information."""

    def __init__(self, history_item: Dict[str, Any]):
        super().__init__(title="詳細な差分表示")
        self.history_item = history_item

        # Create diff text
        changes = history_item.get("changes", {})
        diff_text = self._create_diff_text(changes)

        self.diff_display: discord.ui.TextInput[Self] = discord.ui.TextInput(
            label="差分内容",
            style=discord.TextStyle.paragraph,
            default=diff_text[:4000],  # Discord limit
            max_length=4000,
            required=False,
        )
        self.add_item(self.diff_display)

    def _create_diff_text(self, changes: Dict[str, Any]) -> str:
        """Create formatted diff text."""
        diff_lines = []

        if "title" in changes:
            title_change = changes["title"]
            diff_lines.extend(
                [
                    "=== タイトル変更 ===",
                    f"- {title_change['before']}",
                    f"+ {title_change['after']}",
                    "",
                ]
            )

        if "content" in changes:
            content_change = changes["content"]
            diff_lines.extend(
                [
                    "=== 内容変更 ===",
                ]
            )
            # Add first few lines of diff
            diff_content = content_change.get("diff", [])
            diff_lines.extend(diff_content[:30])  # Limit lines
            if len(diff_content) > 30:
                diff_lines.append("... (差分が長すぎるため省略)")
            diff_lines.append("")

        if "tags" in changes:
            tags_change = changes["tags"]
            diff_lines.extend(
                [
                    "=== タグ変更 ===",
                    f"追加: {', '.join(tags_change['added']) if tags_change['added'] else 'なし'}",
                    f"削除: {', '.join(tags_change['removed']) if tags_change['removed'] else 'なし'}",
                ]
            )

        return "\n".join(diff_lines)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission (close modal)."""
        await interaction.response.defer()
