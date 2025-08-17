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

#### Phase 1-2 (MVP基盤)
- **言語**: Python 3.11+
- **フレームワーク**: discord.py 2.3+
- **基本ライブラリ**:
  - aiohttp (非同期HTTP通信)
  - aiosqlite (軽量DB)
  - Pydantic (設定管理・バリデーション)
  - Python標準logging (ログ)
  - pytest + pytest-asyncio (テスト)
  - Black, isort, flake8, mypy (コード品質)
- **ツール**:
  - Poetry (依存関係管理)
  - GitHub Actions (CI)
  - Railway (PaaS ホスティング)

#### Phase 3-4 (拡張時に検討)
- PyGithub → 非同期GitHub APIクライアント実装
- SQLAlchemy + Alembic (複雑なデータ構造が必要になった場合)
- Structlog (外部ログサービス連携時)
- Docker (マルチ環境デプロイ時)

## 2. コンポーネント設計

### 2.1 コンポーネント一覧

| コンポーネント名 | 責務 | 依存関係 | 実装Phase |
|---|---|---|---|
| BotCore | Bot初期化、Cog管理、イベント処理 | ConfigManager, LoggerService | Phase 1 |
| ConfigManager | 設定読み込み（起動時のみ）、環境管理、バリデーション | Pydantic | Phase 1 |
| LoggerService | 標準ログ、エラー記録 | Python標準logging | Phase 1 |
| DatabaseService | 軽量DB操作（Key-Value） | aiosqlite | Phase 2 |
| GitHubService | 非同期GitHub API操作、レート制限管理、キャッシュ | aiohttp, aiocache | Phase 3 |
| GeneralCog | 基本コマンド（ping, help, status） | BotCore | Phase 1 |
| GitHubCog | GitHub連携コマンド | GitHubService, DatabaseService | Phase 3 |
| VoiceCog | 音声処理、OpenAI API連携 | OpenAI API | Phase 4 |

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

- **目的**: 起動時の設定読み込みとバリデーション
- **公開インターフェース**:
  ```python
  class ConfigManager:
      @staticmethod
      def load_config(env: str = "production") -> BotConfig
      @staticmethod
      def validate_config(config: dict) -> BotConfig
      # Hot reload機能は削除（YAGNI原則）
  ```
- **内部実装方針**:
  - Pydanticベースの型安全な設定
  - 環境変数と.envファイルの階層管理
  - 起動時に一度だけ読み込み（再起動で設定変更を反映）

#### GitHubService

- **目的**: 非同期GitHub API操作とレート制限管理
- **公開インターフェース**:
  ```python
  from abc import ABC, abstractmethod

  class IGitHubService(ABC):  # テスト可能性のための抽象インターフェース
      @abstractmethod
      async def create_pr(...) -> PullRequest: ...

  class GitHubService(IGitHubService):
      def __init__(self, token: str, session: aiohttp.ClientSession, cache: aiocache.Cache)
      async def create_pr(self, repo: str, title: str, body: str,
                         files: Dict[str, str]) -> PullRequest
      async def create_branch(self, repo: str, branch_name: str,
                            base_branch: str = "main") -> Branch
      async def commit_files(self, repo: str, branch: str,
                           files: Dict[str, str], message: str) -> Commit
  ```
- **内部実装方針**:
  - aiohttp による完全非同期処理
  - ETag活用とキャッシュによるレート制限対策
  - 指数バックオフ付きリトライ機構
  - カスタム例外（RateLimitExceeded, RepositoryNotFound等）

#### DatabaseService

- **目的**: 軽量なKey-Valueデータ永続化
- **公開インターフェース**:
  ```python
  class DatabaseService:
      def __init__(self, db_path: str = "nescord.db")
      async def initialize(self) -> None
      async def get(self, key: str) -> Optional[str]
      async def set(self, key: str, value: str) -> None
      async def delete(self, key: str) -> None
      async def get_json(self, key: str) -> Optional[dict]
      async def set_json(self, key: str, value: dict) -> None
  ```
- **内部実装方針**:
  - aiosqlite による軽量DB実装
  - シンプルなKey-Valueテーブル構造
  - JSONシリアライズ対応
  - 将来的なマイグレーションはSQL文で管理

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
# グローバルエラーハンドラによる一元管理
class BotCore(commands.Bot):
    async def on_command_error(self, ctx: Context, error: Exception):
        """Discord.pyのグローバルエラーハンドラ"""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❓ コマンドが見つかりません")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ 必要な引数が不足: {error.param.name}")
        elif isinstance(error, RateLimitExceeded):
            await ctx.send("⏳ APIレート制限中です。少し待ってから再試行してください")
        else:
            logger.error(f"Unexpected error: {error}", exc_info=True)
            await ctx.send("❌ 予期せぬエラーが発生しました")
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

- **カバレッジ目標**:
  - Phase 1-2: 60%以上（基本機能の動作確認重視）
  - Phase 3-4: 80%以上（安定性向上）
- **テストフレームワーク**: pytest + pytest-asyncio + pytest-mock
- **テスト構成**:
  ```python
  tests/
  ├── unit/
  │   ├── test_config_manager.py
  │   ├── test_database_service.py  # Phase 2
  │   └── test_github_service.py    # Phase 3
  ├── integration/
  │   ├── test_general_cog.py        # Phase 1
  │   ├── test_github_cog.py         # Phase 3
  │   └── test_bot_lifecycle.py      # Phase 1
  └── fixtures/
      ├── config_samples.py
      └── mock_github_responses.py    # Phase 3
  ```

### 7.2 統合テスト

```python
class IntegrationTestSuite:
    # Phase 1
    async def test_bot_startup_and_commands(self)
    # Phase 3
    async def test_end_to_end_pr_creation(self)
    async def test_rate_limit_handling(self)
    # Phase 4
    async def test_error_recovery_scenarios(self)
```

## 8. パフォーマンス最適化

### 8.1 想定される負荷

- **同時実行**: 10-50 Discord コマンド/分
- **GitHub API**: 5000 リクエスト/時（認証済みレート制限）
- **メモリ使用量**: < 512MB (Railway Free Plan制限)
- **応答時間**: < 5秒（GitHub PR作成）

### 8.2 最適化方針

```python
class GitHubService:
    def __init__(self, token: str):
        # 接続プール管理
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"token {token}"},
            connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
        )
        # キャッシュ設定（ETag活用）
        self.cache = aiocache.SimpleMemoryCache()
        self.etag_cache: Dict[str, str] = {}

    async def _request_with_cache(self, url: str) -> dict:
        """ETagを使用した条件付きリクエスト"""
        headers = {}
        if url in self.etag_cache:
            headers["If-None-Match"] = self.etag_cache[url]

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 304:  # Not Modified
                return await self.cache.get(url)
            elif resp.status == 200:
                data = await resp.json()
                if etag := resp.headers.get("ETag"):
                    self.etag_cache[url] = etag
                    await self.cache.set(url, data, ttl=300)
                return data
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

## 11. 実装上の重要な設計判断

### 11.1 技術選定の根拠

#### なぜPyGithubではなくaiohttp直接実装か
- **PyGithubは同期ライブラリ**: Discord Botの非同期処理をブロックする
- **柔軟性**: GitHub APIの新機能への即座の対応
- **キャッシュ制御**: ETagベースの条件付きリクエストを完全制御
- **レート制限管理**: 429エラーのリトライ戦略を柔軟に実装

#### なぜSQLAlchemyではなくaiosqliteか
- **シンプルさ**: Key-Value程度のデータにORMは過剰
- **学習曲線**: 新規参加者が理解しやすい
- **依存関係**: ライブラリ依存を最小限に
- **将来性**: 複雑化したら段階的に移行可能

#### なぜStructlogではなく標準loggingか
- **YAGNI原則**: 構造化ログの必要性が明確でない
- **設定の簡潔さ**: 標準loggingは設定がシンプル
- **互換性**: 他のライブラリとの統合が容易
- **移行容易性**: 必要時にStructlogへ移行可能

### 11.2 アーキテクチャパターン

#### 依存性注入（DI）
```python
class BotCore(commands.Bot):
    def __init__(self, config: BotConfig, services: ServiceContainer):
        self.config = config
        self.services = services  # 全サービスをコンテナで管理
        super().__init__(...)
```

#### インターフェース分離
```python
# 抽象インターフェースでテスト可能性を確保
class IGitHubService(ABC):
    @abstractmethod
    async def create_pr(...): ...

# 本番用実装
class GitHubService(IGitHubService): ...

# テスト用モック
class MockGitHubService(IGitHubService): ...
```

### 11.3 非機能要件の実装戦略

#### セキュリティ
- **トークン管理**: 環境変数のみ、ハードコード禁止
- **入力検証**: Pydanticによる型検証 + カスタムバリデータ
- **ログマスキング**: センシティブ情報の自動マスク

#### 可用性
- **グレースフルシャットダウン**: SIGTERMハンドリング
- **ヘルスチェック**: `/health`エンドポイント実装
- **エラー回復**: 接続断時の自動再接続

#### 保守性
- **設定の外部化**: 環境変数と設定ファイルの分離
- **バージョニング**: Semantic Versioning準拠
- **ドキュメント**: docstring + 型ヒント必須

## 12. Phase別実装方針

### Phase 1: MVP基盤 + 最初の機能（2週間）
- **Week 1**:
  - BotCore, ConfigManager (シンプル版), LoggerService (標準logging)
  - GeneralCog (ping, help, status)
  - GitHub Actions CI設定
- **Week 2**:
  - 簡単な拡張コマンド実装（サーバー情報表示等）
  - エラーハンドリング基盤
  - Railwayへの手動デプロイ

### Phase 2: 開発基盤強化 + 機能追加（2週間）
- **Week 1**:
  - DatabaseService (aiosqlite版)
  - テスト基盤構築 (pytest + pytest-asyncio)
  - コード品質ツール統合 (black, flake8, mypy)
- **Week 2**:
  - ログ閲覧コマンド等の新機能
  - 設定永続化機能

### Phase 3: GitHub連携機能 + CD導入（2週間）
- **Week 1**:
  - GitHubService (aiohttp + aiocache版)
  - レート制限管理、キャッシュ実装
  - Railway CDパイプライン
- **Week 2**:
  - GitHubCog 実装
  - Obsidian VaultへのPR作成機能
  - 統合テスト

### Phase 4: 運用基盤完成 + 本格運用（2週間）
- **Week 1**:
  - VoiceCog (OpenAI API連携)
  - ヘルスチェックエンドポイント
  - メトリクス収集
- **Week 2**:
  - ドキュメント整備
  - パフォーマンスチューニング
  - 本番環境最適化
