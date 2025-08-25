# 詳細設計書 - テキストメッセージ処理機能 with GitHub連携Fleeting Note

## 1. アーキテクチャ概要

### 1.1 システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│                        Discord User                          │
└─────────────┬───────────────────────┬───────────────────────┘
              │                       │
        /note command            !note prefix
              │                       │
              ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Voice Cog (拡張)                          │
│  ┌────────────────────────────────────────────────────┐     │
│  │  既存メソッド (再利用)                              │     │
│  │  - process_with_ai(): GPT処理                      │     │
│  │  - TranscriptionView: UI基盤                       │     │
│  └────────────────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────────┐     │
│  │  新規メソッド                                      │     │
│  │  - handle_text_message(): テキスト処理            │     │
│  │  - _format_fleeting_note(): Fleeting Note形式     │     │
│  │  - note_command(): Slash Command                   │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            FleetingNoteView (TranscriptionView拡張)         │
│  - Fleeting Note形式への変換                                │
│  - vault仕様準拠のフォーマット                              │
│  - 保存ボタンハンドリング                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         ObsidianGitHubService (Phase 3実装済み - 再利用)     │
│  - save_to_obsidian(): ファイル保存                         │
│  - SecurityValidator: 入力検証                              │
│  - BatchProcessor: バッチ処理                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Repository                         │
│            (mhcp0001/obsidian-vault/Fleeting Notes/)        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技術スタック

- **言語**: Python 3.11/3.12
- **フレームワーク**: discord.py 2.3+
- **ライブラリ**:
  - openai v1.99.9 (GPT処理)
  - pyyaml (YAML frontmatter生成)
  - aiosqlite (既存のキュー管理)
- **既存サービス**:
  - ObsidianGitHubService (Phase 3実装済み)
  - SecurityValidator (入力検証)
  - BatchProcessor (バッチ同期)

## 2. コンポーネント設計

### 2.1 コンポーネント一覧

| コンポーネント名 | 責務 | 依存関係 |
|-----------------|------|----------|
| Voice Cog | テキスト/音声処理の統合管理 | OpenAI, ObsidianGitHubService |
| handle_text_message | テキストメッセージ処理 | process_with_ai, _format_fleeting_note |
| _format_fleeting_note | Fleeting Note形式生成 | なし |
| FleetingNoteView | UI表示と保存ボタン管理 | TranscriptionView, ObsidianGitHubService |
| ObsidianGitHubService | GitHub保存処理 | SecurityValidator, BatchProcessor |

### 2.2 各コンポーネントの詳細

#### Voice Cog拡張

- **目的**: テキストメッセージ処理機能の追加
- **公開インターフェース**:
```python
class Voice(commands.Cog):
    # 新規メソッド
    async def handle_text_message(
        self,
        message: discord.Message,
        text: str
    ) -> None:
        """テキストメッセージをFleeting note化"""

    def _format_fleeting_note(
        self,
        text: str,
        summary: str,
        message: discord.Message,
        note_type: str = "text"
    ) -> str:
        """Fleeting Note形式のマークダウン生成"""

    def _sanitize_username(self, username: str) -> str:
        """ユーザー名をファイル名用にサニタイズ"""

    # Slash Command
    @app_commands.command(name="note", description="テキストをFleeting noteに変換")
    @app_commands.describe(text="変換するテキスト（最大4000文字）")
    async def note_command(
        self,
        interaction: discord.Interaction,
        text: app_commands.Range[str, 1, 4000]
    ) -> None:
        """Slash Commandハンドラー"""
```

- **内部実装方針**:
  - 既存の`process_with_ai`を完全再利用
  - エラーハンドリングは既存パターンを踏襲
  - 非同期処理で応答性を確保

#### FleetingNoteView

- **目的**: Fleeting Note用のUI表示と保存機能
- **公開インターフェース**:
```python
class FleetingNoteView(TranscriptionView):
    def __init__(
        self,
        content: str,
        summary: str,
        obsidian_service: Optional[ObsidianGitHubService],
        note_type: str = "voice",
        message: Optional[discord.Message] = None
    ):
        """初期化処理"""

    def _generate_filename(self, user_name: str) -> str:
        """vault仕様準拠のファイル名生成"""

    async def save_to_obsidian(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """Obsidian保存処理（オーバーライド）"""
```

- **内部実装方針**:
  - TranscriptionViewの機能を最大限継承
  - Fleeting Note仕様に特化した処理のみ追加
  - ファイル名生成ロジックをvault仕様に準拠

## 3. データフロー

### 3.1 データフロー図

```
[ユーザー入力]
    ↓
[テキスト抽出] ← /note or !note
    ↓
[GPT処理] ← process_with_ai (既存)
    ├─ 整形処理
    └─ 要約生成
    ↓
[Fleeting Note形式変換]
    ├─ YAML frontmatter生成
    ├─ コンテンツ構造化
    └─ Discord情報埋め込み
    ↓
[UI表示] ← FleetingNoteView
    ↓
[保存ボタン押下]
    ↓
[ObsidianGitHubService]
    ├─ SecurityValidator検証
    ├─ ファイル名生成
    └─ キューイング
    ↓
[BatchProcessor]
    ↓
[GitHub Repository同期]
```

### 3.2 データ変換

- **入力データ形式**:
  - プレーンテキスト（最大4000文字）
  - Discordメッセージメタデータ

- **処理過程**:
  1. GPT-3.5-turboによる整形・要約
  2. YAML frontmatter付与
  3. Fleeting Note構造化

- **出力データ形式**:
  ```markdown
  ---
  id: 20250821153045
  title: "要約テキスト..."
  type: fleeting_note
  status: fleeting
  tags:
    - capture/
    - discord/
    - discord/text
  context: "Discord #general でのテキストメッセージ"
  source: "Discord Bot NescordBot"
  created: 2025-08-21 15:30
  ---

  # タイトル

  ## 💭 アイデア・思考の断片
  [GPT処理済みテキスト]

  ## 🔗 関連しそうなこと
  -

  ## ❓ 疑問・調べたいこと
  -

  ## 📝 次のアクション
  - [ ] Literature Noteに発展させる
  - [ ] Permanent Noteに昇華する
  - [ ] 関連資料を調査する
  - [ ] アーカイブする

  ---

  ### Discord情報
  - **サーバー**: サーバー名
  - **チャンネル**: チャンネル名
  - **ユーザー**: ユーザー名
  - **メッセージID**: 1234567890
  - **タイプ**: テキストメッセージ

  ---
  *素早く記録することを優先。後で整理・発展させる。*
  ```

## 4. APIインターフェース

### 4.1 内部API

```python
# Voice Cog → ObsidianGitHubService
await self.obsidian_service.save_to_obsidian(
    filename=filename,  # "20250821_1530_discord_text_username.md"
    content=formatted_content,  # Fleeting Note形式のマークダウン
    directory="Fleeting Notes",  # vault仕様準拠
    metadata={
        "type": "fleeting_note",
        "note_type": note_type,  # "text" or "voice"
        "discord_user": str(user),
        "discord_channel": str(channel),
        "created_at": datetime.now().isoformat()
    }
)
```

### 4.2 外部API

```python
# OpenAI GPT API (既存のprocess_with_ai経由)
response = await self.process_with_ai(text)
# returns: {"processed": str, "summary": str}

# Discord Interaction API
await interaction.response.defer()
await interaction.followup.send(embed=embed, view=view)
```

## 5. エラーハンドリング

### 5.1 エラー分類

- **入力エラー**:
  - 空テキスト → "テキストを入力してください"
  - 長すぎるテキスト → 自動分割処理

- **API エラー**:
  - OpenAI レート制限 → 既存のレート制限処理を適用
  - タイムアウト → 30秒タイムアウトで適切なメッセージ

- **保存エラー**:
  - GitHub API障害 → ローカルキューで保持
  - 権限エラー → SecurityValidatorで事前検証

### 5.2 エラー通知

```python
try:
    # 処理
except TimeoutError:
    await message.reply("⏱️ 処理がタイムアウトしました。もう一度お試しください。")
except ValueError as e:
    await message.reply(f"❌ 入力エラー: {str(e)}")
except Exception as e:
    logger.error(f"テキスト処理エラー: {e}")
    await message.reply("❌ エラーが発生しました。管理者にお問い合わせください。")
```

## 6. セキュリティ設計

### 6.1 入力検証

- **SecurityValidator活用**:
  - ファイル名のサニタイズ
  - XSS攻撃の検出と防止
  - インジェクション攻撃の防止

### 6.2 データ保護

- **APIキー管理**: 環境変数で管理
- **ユーザー情報**: 最小限の情報のみ保存
- **テキスト内容**: SecurityValidatorで危険な内容を検証

## 7. テスト戦略

### 7.1 単体テスト

- **カバレッジ目標**: 70%以上
- **テストフレームワーク**: pytest + pytest-asyncio
- **テスト項目**:
  ```python
  # test_text_message.py
  async def test_handle_text_message_success()
  async def test_handle_text_message_empty()
  async def test_handle_text_message_long_text()
  async def test_format_fleeting_note()
  async def test_sanitize_username()
  async def test_note_command()
  ```

### 7.2 統合テスト

```python
# test_fleeting_note_integration.py
async def test_text_to_github_flow():
    """テキスト入力からGitHub保存までの統合テスト"""

async def test_fleeting_note_format_compliance():
    """Fleeting Note仕様準拠の検証"""

async def test_concurrent_text_processing():
    """複数同時処理のテスト"""
```

## 8. パフォーマンス最適化

### 8.1 想定される負荷

- **同時リクエスト**: 最大10件/分
- **テキストサイズ**: 平均500文字、最大4000文字
- **応答時間目標**: 3秒以内（初期応答）

### 8.2 最適化方針

- **非同期処理**: すべての外部API呼び出しを非同期化
- **キャッシング**: GPT処理結果の短期キャッシュ（重複防止）
- **バッチ処理**: ObsidianGitHubServiceの既存バッチ機能活用

## 9. デプロイメント

### 9.1 デプロイ構成

- **既存のRailway環境にそのまま展開**
- **追加の環境変数不要**（既存のOPENAI_API_KEY等を利用）
- **Dockerfileの変更不要**

### 9.2 設定管理

```python
# 既存の環境変数を再利用
OPENAI_API_KEY          # GPT処理用
GITHUB_TOKEN           # GitHub保存用
OBSIDIAN_REPO_URL      # vault リポジトリ

# オプション設定（config.py経由）
MAX_TEXT_LENGTH = 4000  # 最大テキスト長
FLEETING_NOTE_DIR = "Fleeting Notes"  # 保存先ディレクトリ
```

## 10. 実装上の注意事項

### 10.1 既存コードとの整合性

- **process_with_ai**メソッドは変更せず、そのまま利用
- **TranscriptionView**の基本構造を維持し、必要な部分のみオーバーライド
- **ObsidianGitHubService**のインターフェースは変更しない

### 10.2 Fleeting Note仕様の厳守

- YAML frontmatterの形式を厳密に守る
- ファイル名規則（`YYYYMMDD_HHMM_discord_text_[user_name].md`）を確実に適用
- `Fleeting Notes/`ディレクトリへの配置を徹底

### 10.3 エラー処理の一貫性

- 既存の音声処理と同じエラーメッセージフォーマットを使用
- ログ出力は既存のロガーを使用
- ユーザーへのフィードバックは絵文字付きで統一

### 10.4 テスト実装の優先順位

1. Fleeting Note形式の正確性テスト
2. エンドツーエンドの統合テスト
3. エラーケースのテスト

---

**作成日**: 2025-08-21
**設計者**: Claude Code
**レビューステータス**: 承認待ち
**実装見積もり**: 45分（既存資産85%活用）
