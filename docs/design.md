# 詳細設計書 - NescordBot 開発・運用基盤整備

## 1. アーキテクチャ概要

### 1.1 システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│                     Discord Platform                        │
└─────────────────┬───────────────────────────────────────────┘
                  │ Discord API
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    NescordBot                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    Core     │  │   GitHub    │  │   Voice     │         │
│  │     Cog     │  │    Cog      │  │    Cog      │   ...   │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                Bot Framework Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Config    │  │   Logger    │  │  Database   │         │
│  │  Manager    │  │   Service   │  │   Service   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                Infrastructure Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   GitHub    │  │   OpenAI    │  │  External   │         │
│  │    API      │  │    API      │  │  Services   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Railway PaaS Platform                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    App      │  │  Database   │  │   Secrets   │         │
│  │ Container   │  │  (SQLite)   │  │  Manager    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技術スタック

- **言語**: Python 3.11+
- **フレームワーク**: discord.py 2.3+
- **ライブラリ**: 
  - PyGithub (GitHub API操作)
  - SQLAlchemy (ORM)
  - Pydantic (設定管理・バリデーション)
  - Structlog (構造化ログ)
  - pytest (テスト)
  - Black, isort, flake8, mypy (コード品質)
- **ツール**: 
  - Poetry (依存関係管理)
  - Docker (コンテナ化)
  - GitHub Actions (CI/CD)
  - Railway (PaaS ホスティング)

## 2. コンポーネント設計

### 2.1 コンポーネント一覧

| コンポーネント名 | 責務 | 依存関係 |
|---|---|---|
| BotCore | Bot初期化、Cog管理、イベント処理 | ConfigManager, LoggerService |
| ConfigManager | 設定読み込み、環境管理、バリデーション | Pydantic |
| LoggerService | 構造化ログ、エラー追跡、監視 | Structlog |
| DatabaseService | DB接続、マイグレーション、ORM | SQLAlchemy |
| GitHubService | GitHub API操作、PR作成、認証 | PyGithub |
| GeneralCog | 基本コマンド（ping, help, status） | BotCore |
| GitHubCog | GitHub連携コマンド | GitHubService, DatabaseService |
| VoiceCog | 音声処理、OpenAI API連携 | OpenAI API |

### 2.2 各コンポーネントの詳細

#### BotCore

- **目的**: Discord Botの中核機能とCogライフサイクル管理
- **公開インターフェース**:
  ```python
  class NescordBot(commands.Bot):
      def __init__(self, config: BotConfig)
      async def setup_hook(self) -> None
      async def load_cogs(self) -> None
      async def on_ready(self) -> None
      async def on_error(self, event: str, *args, **kwargs) -> None
  ```
- **内部実装方針**: 
  - Cogの動的ロード・アンロード対応
  - エラーハンドリングの一元化
  - 設定に基づく機能ON/OFF制御

#### ConfigManager

- **目的**: 環境別設定管理とバリデーション
- **公開インターフェース**:
  ```python
  class ConfigManager:
      @staticmethod
      def load_config(env: str = "production") -> BotConfig
      @staticmethod
      def validate_config(config: dict) -> BotConfig
      def reload_config(self) -> None
  ```
- **内部実装方針**: 
  - Pydanticベースの型安全な設定
  - 環境変数とファイル設定の階層管理
  - Hot reloadサポート

#### GitHubService

- **目的**: GitHub API操作の抽象化とエラーハンドリング
- **公開インターフェース**:
  ```python
  class GitHubService:
      def __init__(self, token: str, rate_limit_manager: RateLimitManager)
      async def create_pr(self, repo: str, title: str, body: str, 
                         files: Dict[str, str]) -> PullRequest
      async def create_branch(self, repo: str, branch_name: str, 
                            base_branch: str = "main") -> Branch
      async def commit_files(self, repo: str, branch: str, 
                           files: Dict[str, str], message: str) -> Commit
  ```
- **内部実装方針**: 
  - レート制限の自動管理
  - リトライ機構とエラー回復
  - 非同期処理対応

#### DatabaseService

- **目的**: データ永続化とマイグレーション管理
- **公開インターフェース**:
  ```python
  class DatabaseService:
      def __init__(self, database_url: str)
      async def initialize(self) -> None
      async def migrate(self, version: str = "head") -> None
      def get_session(self) -> AsyncSession
  ```
- **内部実装方針**: 
  - SQLAlchemy 2.0+ 非同期ORM
  - Alembicベースのマイグレーション
  - 接続プール管理

## 3. データフロー

### 3.1 GitHub連携機能のデータフロー

```
Discord Message → Command Parser → GitHub Cog → GitHub Service
                                        ↓
Database ← Content Formatter ← PR Creator ← GitHub API
    ↓
Log Service ← Response Formatter ← Discord Response
```

### 3.2 データ変換

- **入力データ形式**: Discord Message オブジェクト
- **処理過程**: 
  1. コマンド解析 (discord.py)
  2. パラメータバリデーション (Pydantic)
  3. ビジネスロジック実行
  4. GitHub API呼び出し
  5. 結果のフォーマット
- **出力データ形式**: Discord Embed + GitHub PR URL

## 4. APIインターフェース

### 4.1 内部API

```python
# Cog間通信用のイベントシステム
class BotEvents:
    PR_CREATED = "pr_created"
    CONFIG_RELOADED = "config_reloaded"
    ERROR_OCCURRED = "error_occurred"

# 共通データモデル
@dataclass
class PRCreationResult:
    pr_url: str
    pr_number: int
    repository: str
    created_at: datetime
    status: PRStatus
```

### 4.2 外部API

```python
# GitHub REST API v4 ラッパー
class GitHubAPIClient:
    BASE_URL = "https://api.github.com"
    
    async def create_pull_request(self, repo: str, data: PRData) -> dict
    async def create_blob(self, repo: str, content: str, encoding: str) -> dict
    async def create_tree(self, repo: str, tree_data: List[TreeItem]) -> dict
    async def create_commit(self, repo: str, commit_data: CommitData) -> dict

# Discord API ラッパー（discord.py準拠）
class DiscordResponder:
    async def send_embed(self, channel: TextChannel, embed: Embed) -> Message
    async def send_error(self, channel: TextChannel, error: str) -> Message
```

## 5. エラーハンドリング

### 5.1 エラー分類

- **APIError**: GitHub/Discord API関連エラー
  - 対処方法: リトライ機構、フォールバック処理、ユーザー通知
- **ConfigError**: 設定ファイル・環境変数エラー  
  - 対処方法: デフォルト値使用、起動時検証、管理者アラート
- **ValidationError**: 入力データ検証エラー
  - 対処方法: ユーザーフレンドリーなエラーメッセージ、使用例提示
- **DatabaseError**: DB接続・操作エラー
  - 対処方法: 接続再試行、読み取り専用モード、データ整合性確保

### 5.2 エラー通知

```python
@dataclass
class ErrorReport:
    error_type: str
    error_message: str
    context: Dict[str, Any]
    timestamp: datetime
    user_id: Optional[int]
    channel_id: Optional[int]
    
class ErrorReporter:
    async def report_error(self, error: Exception, context: ErrorContext)
    async def send_user_friendly_error(self, channel: TextChannel, error: str)
    async def alert_administrators(self, error: CriticalError)
```

## 6. セキュリティ設計

### 6.1 認証・認可

```python
class SecurityManager:
    def validate_github_token(self, token: str) -> bool
    def check_user_permissions(self, user_id: int, command: str) -> bool
    def sanitize_user_input(self, input_data: str) -> str
```

### 6.2 データ保護

- **トークン管理**: 環境変数での管理、Railway Secrets使用
- **ログセキュリティ**: 機密情報のマスキング、ログローテーション
- **入力検証**: SQLインジェクション防止、XSS対策、ファイルパス検証

## 7. テスト戦略

### 7.1 単体テスト

- **カバレッジ目標**: 80%以上
- **テストフレームワーク**: pytest + pytest-asyncio + pytest-mock
- **テスト構成**:
  ```python
  tests/
  ├── unit/
  │   ├── test_config_manager.py
  │   ├── test_github_service.py
  │   └── test_database_service.py
  ├── integration/
  │   ├── test_github_cog.py
  │   └── test_bot_lifecycle.py
  └── fixtures/
      ├── config_samples.py
      └── mock_responses.py
  ```

### 7.2 統合テスト

```python
class IntegrationTestSuite:
    async def test_end_to_end_pr_creation(self)
    async def test_error_recovery_scenarios(self)
    async def test_configuration_reload(self)
```

## 8. パフォーマンス最適化

### 8.1 想定される負荷

- **同時実行**: 10-50 Discord コマンド/分
- **GitHub API**: 100 リクエスト/時（レート制限内）
- **メモリ使用量**: < 512MB (Railway制限)
- **応答時間**: < 5秒（GitHub PR作成）

### 8.2 最適化方針

```python
class PerformanceOptimizer:
    # 接続プール管理
    github_client_pool: aiohttp.ClientSession
    database_pool: AsyncEngine
    
    # キャッシュ戦略
    @lru_cache(maxsize=100)
    def get_repository_info(self, repo_name: str) -> RepoInfo
    
    # 非同期処理
    async def batch_process_requests(self, requests: List[Request]) -> List[Result]
```

## 9. デプロイメント

### 9.1 デプロイ構成

```yaml
# railway.toml
[build]
builder = "dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "always"

[env]
PYTHON_VERSION = "3.11"
```

### 9.2 設定管理

```python
# config/settings.py
class BotConfig(BaseSettings):
    # Discord設定
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_guild_id: Optional[int] = Field(None, env="DISCORD_GUILD_ID")
    
    # GitHub設定  
    github_token: str = Field(..., env="GITHUB_TOKEN")
    target_repository: str = Field(..., env="TARGET_REPOSITORY")
    
    # Database設定
    database_url: str = Field("sqlite:///nescord.db", env="DATABASE_URL")
    
    # Railway設定
    railway_environment: str = Field("production", env="RAILWAY_ENVIRONMENT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

## 10. 実装上の注意事項

### 10.1 コーディング規約

- **型ヒント**: 全ての関数・メソッドに型アノテーション必須
- **エラーハンドリング**: 必ず適切な例外処理を実装
- **ログ出力**: 構造化ログを使用し、十分な文脈情報を含める
- **設定管理**: ハードコーディング禁止、環境変数で管理

### 10.2 パフォーマンス

- **非同期処理**: I/O操作は必ず非同期で実装
- **リソース管理**: 適切なコンテキストマネージャー使用
- **メモリ管理**: 大きなファイルはストリーミング処理

### 10.3 セキュリティ

- **入力検証**: 全てのユーザー入力をバリデーション
- **認証情報**: 絶対にログ出力やエラーメッセージに含めない
- **権限管理**: 最小権限の原則を適用

### 10.4 テスト

- **モック使用**: 外部API呼び出しは必ずモック
- **テストデータ**: 本番データを絶対に使用しない
- **CI/CD**: 全てのテストがパスしてからマージ

### 10.5 監視・運用

- **ヘルスチェック**: `/health` エンドポイントの実装
- **メトリクス**: 重要な処理の実行時間と成功率を記録
- **アラート**: 重要なエラーは即座に通知

## 11. Phase別実装方針

### Phase 1: MVP基盤（2週間）
- BotCore, ConfigManager, LoggerService の基本実装
- GeneralCog (ping, help, status) の実装
- 基本的なCI/CD構築

### Phase 2: 開発基盤強化（2週間）  
- DatabaseService, テスト基盤の実装
- コード品質ツールの統合
- 設定管理システムの完成

### Phase 3: GitHub連携機能（2週間）
- GitHubService, GitHubCog の実装  
- PR作成機能の完成
- Railway自動デプロイの実装

### Phase 4: 運用基盤完成（2週間）
- 監視・アラートシステム
- パフォーマンス最適化
- ドキュメント整備と運用手順確立