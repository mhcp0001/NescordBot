# NescordBot アーキテクチャ設計書

## 🏗️ システム全体概要

NescordBotは、Discord Bot、音声認識AI、GitHub統合、Obsidian連携を統合した高度な非同期システムです。Phase 3において、世界クラスのCI/CD基盤と共に完全なObsidian GitHub統合機能を実装しました。

### 設計原則
- **非同期ファースト**: 全操作がasync/awaitベース
- **依存関係逆転**: 抽象化層による疎結合設計
- **セキュリティ最優先**: 全入力の検証・サニタイゼーション
- **高可用性**: 永続化キュー・エラー回復機能
- **拡張性**: プラグイン型Cogアーキテクチャ

## 🎯 アーキテクチャ全体図

```
┌─────────────────────────────────────────────────────────────┐
│                    Discord Client Layer                     │
├─────────────────────────────────────────────────────────────┤
│                     NescordBot Core                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ General Cog │  │ Admin Cog   │  │ Voice Cog   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────┤
│                  Service Container                          │
│  ┌─────────────────┐  ┌──────────────────────────────────┐ │
│  │ Core Services   │  │    Integration Services           │ │
│  │ ┌─────────────┐ │  │ ┌──────────────────────────────┐ │ │
│  │ │DatabaseSvc  │ │  │ │ ObsidianGitHubService        │ │ │
│  │ │SecurityVal  │ │  │ │ ┌────────────┐ ┌───────────┐ │ │ │
│  │ │LoggerSvc    │ │  │ │ │GitHubAuth  │ │BatchProc  │ │ │ │
│  │ └─────────────┘ │  │ │ │Manager     │ │essor      │ │ │ │
│  └─────────────────┘  │ │ └────────────┘ └───────────┘ │ │ │
│                       │ │ ┌────────────┐ ┌───────────┐ │ │ │
│                       │ │ │PersistentQ │ │GitOperat  │ │ │ │
│                       │ │ │ueue        │ │ionService │ │ │ │
│                       │ │ └────────────┘ └───────────┘ │ │ │
│                       │ └──────────────────────────────┘ │ │
│                       └──────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    External Services                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   OpenAI    │  │   GitHub    │  │  Obsidian   │        │
│  │   Whisper   │  │     API     │  │    Vault    │        │
│  │     GPT     │  │             │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 コアコンポーネント詳細

### 1. NescordBot Core (`src/nescordbot/bot.py`)

```python
class NescordBot(commands.Bot):
    """Discord Bot のメインエントリーポイント"""

    def __init__(self, config: BotConfig, service_container: ServiceContainer):
        # Discord.py Bot初期化
        # Service Container注入
        # Cog自動ロード

    async def setup_hook(self):
        # サービス初期化
        # データベース接続
        # 外部API認証
```

**設計特徴**:
- **依存関係注入**: ServiceContainerによる疎結合
- **グレースフルシャットダウン**: リソース適切解放
- **エラー処理**: グローバルエラーハンドラー統合

### 2. BotRunner & ServiceContainer (`src/nescordbot/main.py`)

```python
class BotRunner:
    """Bot ライフサイクル管理"""

    async def start(self):
        # 設定読み込み
        # サービス初期化
        # Bot起動

    async def stop(self):
        # グレースフルシャットダウン
        # リソースクリーンアップ

class ServiceContainer:
    """依存関係注入コンテナ"""

    def register_service(self, service_type: Type[T], instance: T):
    def get_service(self, service_type: Type[T]) -> T:
```

**責務**:
- アプリケーションライフサイクル管理
- サービス依存関係解決
- 設定ベースの動的初期化

## 🛡️ セキュリティ層

### SecurityValidator (`src/nescordbot/services/security.py`)

```python
class SecurityValidator:
    """包括的セキュリティ検証システム"""

    # XSS/インジェクション対策
    DANGEROUS_PATTERNS = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'(\bUNION\b|\bSELECT\b|\bINSERT\b)',
    ]

    def validate_github_content(self, content: str) -> bool:
        """GitHub投稿内容の安全性検証"""

    def sanitize_file_path(self, path: str) -> str:
        """ファイルパスの正規化・検証"""

    def check_dangerous_patterns(self, text: str) -> List[str]:
        """危険パターンの検出"""
```

**セキュリティ機能**:
- **入力検証**: 全ユーザー入力の包括的検証
- **パターンマッチング**: 既知攻撃パターンの検出
- **ファイルパス検証**: ディレクトリトラバーサル防止
- **統合設計**: 全サービスでの一貫した適用

## 🗃️ データ永続化層

### 1. DatabaseService (`src/nescordbot/services/database.py`)

```python
class DatabaseService:
    """非同期SQLiteデータベース管理"""

    async def get(self, key: str) -> Optional[str]:
    async def set(self, key: str, value: str) -> None:
    async def get_json(self, key: str) -> Optional[Dict]:
    async def set_json(self, key: str, value: Dict) -> None:
    async def execute(self, query: str, params: tuple = ()) -> Any:
```

### 2. PersistentQueue (`src/nescordbot/services/persistent_queue.py`)

```python
class PersistentQueue:
    """高信頼性永続化キューシステム"""

    async def enqueue(self, item: Dict[str, Any], priority: int = 0) -> str:
        """優先度付きアイテム追加"""

    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """FIFO/優先度ベースデキュー"""

    async def dead_letter_queue(self) -> List[Dict[str, Any]]:
        """失敗アイテムの管理"""

    async def retry_failed_items(self, max_attempts: int = 3) -> int:
        """自動リトライ機能"""
```

**技術特徴**:
- **SQLiteトランザクション**: ACID特性保証
- **Dead Letter Queue**: 失敗アイテムの隔離・分析
- **優先度キューイング**: 重要度ベース処理順序
- **自動リトライ**: 指数バックオフ戦略

## 🔗 GitHub統合層

### 1. GitHubAuthManager (`src/nescordbot/services/github_auth.py`)

```python
class GitHubAuthManager:
    """GitHub認証・レート制限管理"""

    async def authenticate_with_pat(self, token: str) -> bool:
        """Personal Access Token認証"""

    async def authenticate_with_app(self, app_id: str, private_key: str) -> bool:
        """GitHub App認証"""

    async def refresh_token(self) -> str:
        """トークン自動リフレッシュ"""

    async def get_rate_limit_status(self) -> Dict[str, int]:
        """レート制限状況取得"""
```

### 2. GitOperationService (`src/nescordbot/services/git_operations.py`)

```python
class GitOperationService:
    """安全なGit操作抽象化"""

    async def safe_clone(self, repo_url: str, target_dir: str) -> bool:
        """セキュリティ検証付きクローン"""

    async def create_branch(self, branch_name: str) -> bool:
        """ブランチ作成・切り替え"""

    async def commit_changes(self, message: str, files: List[str]) -> str:
        """原子性コミット操作"""

    async def push_to_remote(self, branch: str) -> bool:
        """リモートプッシュ（エラー回復付き）"""
```

**安全性機能**:
- **パス検証**: SecurityValidator統合
- **原子性操作**: 部分失敗時の自動ロールバック
- **エラー回復**: 自動リトライ・状態復元
- **ログ追跡**: 全操作の詳細記録

### 3. BatchProcessor (`src/nescordbot/services/batch_processor.py`)

```python
class BatchProcessor:
    """統合バッチ処理エンジン"""

    async def process_obsidian_to_github(self, content: str, metadata: Dict) -> str:
        """Obsidian→GitHub統合処理"""

    async def batch_commit_multiple_files(self, files: List[FileData]) -> str:
        """複数ファイル一括コミット"""

    async def schedule_delayed_processing(self, item: Dict, delay: int) -> None:
        """遅延処理スケジューリング"""
```

## 🎭 統合サービス層

### ObsidianGitHubService (`src/nescordbot/services/obsidian_github.py`)

```python
class ObsidianGitHubService:
    """Obsidian-GitHub統合の集大成"""

    def __init__(self,
                 github_auth: GitHubAuthManager,
                 git_ops: GitOperationService,
                 batch_processor: BatchProcessor,
                 persistent_queue: PersistentQueue,
                 security_validator: SecurityValidator):
        # 全統合サービスの依存関係注入

    async def sync_obsidian_note_to_github(self, note_path: str) -> str:
        """Obsidian→GitHub完全同期"""
        # 1. ノート読み込み・検証
        # 2. メタデータ抽出
        # 3. セキュリティ検証
        # 4. GitHub形式変換
        # 5. バッチ処理キューイング
        # 6. Git操作実行
        # 7. 結果追跡・ログ

    async def create_github_issue_from_note(self, content: str) -> int:
        """ノート→Issue自動作成"""

    async def setup_webhook_integration(self) -> bool:
        """リアルタイムWebhook統合"""
```

**統合機能**:
- **全サービス協調**: 5つのコアサービス統合
- **エラー回復**: 各段階での失敗時自動回復
- **監査ログ**: 全操作の完全追跡可能性
- **リアルタイム処理**: Webhook即座反映

## 🤖 Cogアーキテクチャ

### 1. General Cog (`src/nescordbot/cogs/general.py`)
```python
class GeneralCog(commands.Cog):
    """基本コマンド群"""

    @app_commands.command()
    async def help(self, interaction: discord.Interaction):
        """ヘルプ表示"""

    @app_commands.command()
    async def status(self, interaction: discord.Interaction):
        """Bot状態確認"""
```

### 2. Admin Cog (`src/nescordbot/cogs/admin.py`)
```python
class AdminCog(commands.Cog):
    """管理者専用機能"""

    @app_commands.command()
    async def logs(self, interaction: discord.Interaction):
        """ログ閲覧（権限制御付き）"""

    @app_commands.command()
    async def dbstats(self, interaction: discord.Interaction):
        """データベース統計情報"""
```

### 3. Voice Cog (`src/nescordbot/cogs/voice.py`)
```python
class VoiceCog(commands.Cog):
    """音声処理・AI統合"""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """音声メッセージ自動処理"""
        # 1. 音声ファイル検出
        # 2. Whisper文字起こし
        # 3. GPT内容整形
        # 4. Obsidian保存オプション
        # 5. GitHub連携ボタン
```

## 📡 外部API統合

### 1. OpenAI API統合
```python
# Whisper音声認識
async def transcribe_audio(audio_file: str) -> str:
    """音声→テキスト変換"""

# GPT内容処理
async def process_with_gpt(content: str, instruction: str) -> str:
    """AI内容整形"""
```

### 2. GitHub API統合
```python
# GitHub REST API v4
async def create_issue(title: str, body: str, labels: List[str]) -> int:
async def create_pull_request(title: str, body: str, head: str) -> int:
async def commit_file(path: str, content: str, message: str) -> str:
```

### 3. Obsidian統合
```python
# Obsidian Vault操作
async def read_note(path: str) -> Dict[str, Any]:
async def write_note(path: str, content: str, metadata: Dict) -> None:
async def list_notes(pattern: str) -> List[str]:
```

## 🔧 設定管理

### BotConfig (`src/nescordbot/config.py`)
```python
class BotConfig(BaseModel):
    """Pydantic設定モデル"""

    # Discord設定
    discord_token: str
    discord_guild_id: Optional[str] = None

    # AI統合
    openai_api_key: str
    max_audio_size_mb: int = 25
    speech_language: str = "ja-JP"

    # GitHub統合
    github_token: Optional[str] = None
    github_repo_owner: Optional[str] = None
    github_repo_name: Optional[str] = None
    github_base_branch: str = "main"

    # Obsidian統合
    obsidian_vault_path: Optional[str] = None

    # システム設定
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/nescordbot.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

## 🧪 テスト戦略

### テストアーキテクチャ
```
tests/
├── unit/                    # 単体テスト
│   ├── test_config.py
│   ├── test_security.py
│   └── test_services/
├── integration/             # 統合テスト
│   ├── test_obsidian_github.py
│   ├── test_persistent_queue.py
│   └── test_github_auth.py
├── fixtures/               # テストフィクスチャ
│   ├── mock_discord.py
│   ├── mock_github_api.py
│   └── sample_data/
└── conftest.py             # pytest設定
```

### 品質メトリクス
- **テストカバレッジ**: 78%維持
- **並列実行**: pytest-xdist活用
- **モック精度**: 実装ロジック完全準拠
- **実行時間**: 1分30秒（並列化効果）

## 🚀 CI/CD アーキテクチャ

### GitHub Actions パイプライン
```yaml
# .github/workflows/ci.yml
jobs:
  test:           # Python 3.11/3.12 マトリックステスト
  security:       # bandit + safety セキュリティスキャン
  docker-integration-test:  # 本番環境統合テスト
```

### Docker統合環境
```dockerfile
# Dockerfile (環境統一)
FROM python:3.11-slim as builder
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --output requirements.txt

FROM python:3.11-slim as runtime
RUN poetry config virtualenvs.create false \
    && poetry install --only-root
CMD ["poetry", "run", "start"]
```

### Railway自動デプロイ
- **Dockerベースデプロイ**: 環境完全一致
- **自動CI/CDトリガー**: mainブランチプッシュ時
- **環境変数管理**: Railway Web UI統合
- **ヘルスチェック**: 自動監視・復旧

## 📊 パフォーマンス最適化

### 非同期処理最適化
- **Connection Pooling**: aiosqlite/aiohttp
- **バッチ処理**: 複数操作の効率的統合
- **キューイング**: 負荷分散・スループット向上
- **キャッシュ戦略**: 冗長API呼び出し削減

### メモリ管理
- **リソースプール**: 接続・ファイルハンドル管理
- **ガベージコレクション**: 大きなオブジェクトの適切解放
- **メモリ監視**: 使用量追跡・アラート

## 🔮 拡張性・将来性

### プラグインアーキテクチャ
- **Cog動的ロード**: 機能モジュールの追加・削除
- **サービス注入**: 新機能の疎結合統合
- **設定駆動**: 機能有効/無効の動的制御

### スケーラビリティ対応
- **水平スケーリング**: 複数インスタンス対応
- **外部キュー**: Redis/RabbitMQ統合準備
- **マイクロサービス化**: サービス分離の容易性

---

**アーキテクチャ バージョン**: Phase 3完了時点
**最終更新**: 2025-08-21
**設計責任**: Claude Code + NescordBot開発チーム
**次期改善**: Phase 4運用基盤強化対応
