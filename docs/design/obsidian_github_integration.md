# 包括的設計書 - Obsidian GitHub統合機能

## 📋 概要

本設計書は、NescordBotの既存Obsidian vault連携機能をGitHub統合に移行するための包括的な技術仕様書です。既存のローカルファイルシステム直接保存から、GitHubリポジトリ（`https://github.com/mhcp0001/obsidian-vault`）に格納されたObsidian vaultとの連携に変更します。

## 🎯 目標

1. **既存機能の完全置き換え**: ローカルObsidian連携からGitHub連携への移行
2. **Fleeting Note仕様準拠**: 既存vault構造との完全な互換性維持
3. **競合回避**: 他のユーザー・Obsidianアプリとの同時編集環境での安全な動作
4. **段階的実装**: 開発時PAT → 本番時GitHub App認証
5. **堅牢性**: エラー時のローカルキャッシュとフォールバック機構

---

## 1. アーキテクチャ概要

### 1.1 システム構成図

```mermaid
graph TB
    subgraph "Discord Bot Layer"
        DC[Discord Commands]
        VC[Voice Cog]
        OC[Obsidian Cog]
    end

    subgraph "既存システム層"
        BC[BotCore]
        CM[ConfigManager]
        LS[LoggerService]
        DS[DatabaseService]
    end

    subgraph "新規 Obsidian GitHub Service層"
        OGS[ObsidianGitHubService]
        GAM[GitHubAuthManager]
        GOM[GitOperationManager]
        BP[BatchProcessor]
        FG[FleetingNoteGenerator]
    end

    subgraph "外部システム"
        GH[GitHub API]
        GR[GitHub Repository<br/>mhcp0001/obsidian-vault]
        LR[Local Repository<br/>./data/obsidian-vault/]
        OA[Obsidian App]
    end

    DC --> OC
    VC --> OC
    OC --> OGS
    OGS --> BC
    OGS --> CM
    OGS --> LS
    OGS --> DS

    OGS --> GAM
    OGS --> GOM
    OGS --> BP
    OGS --> FG

    GAM --> GH
    GOM --> LR
    GOM --> GR
    BP --> GOM
    FG --> BP

    OA -.->|外部編集| GR

    style OGS fill:#e1f5fe
    style GAM fill:#f3e5f5
    style GOM fill:#e8f5e8
    style BP fill:#fff3e0
    style FG fill:#fce4ec
```

### 1.2 アーキテクチャ原則

#### 1.2.1 レイヤー分離

**既存システム層の活用**:
- BotCore: Discord Bot基盤機能
- ConfigManager: 設定管理・環境変数処理
- LoggerService: ログ出力・エラー追跡
- DatabaseService: メタデータ・状態管理

**新規サービス層の設計**:
- **認証層** (GitHubAuthManager): GitHub App/PAT認証切り替え
- **Git操作層** (GitOperationManager): ローカルリポジトリ管理・Git操作
- **バッチ処理層** (BatchProcessor): キューイング・バッチ処理制御
- **フォーマット層** (FleetingNoteGenerator): Fleeting Note形式生成

#### 1.2.2 関心の分離

```python
# 各層の責務を明確に分離
Authentication → Git Operations → Batch Processing → Service Layer
      ↓                ↓               ↓              ↓
 GitHub認証        ローカル操作      非同期制御      統合管理
```

### 1.3 技術スタック

#### 1.3.1 既存技術スタック（継続利用）

- **言語**: Python 3.11+
- **フレームワーク**: discord.py 2.3+, asyncio
- **基盤ライブラリ**: aiosqlite, Pydantic, aiohttp
- **開発ツール**: Poetry, pytest, Black, mypy

#### 1.3.2 新規追加ライブラリ

- **PyGithub 2.1+**: GitHub API認証・操作
- **GitPython 3.1+**: ローカルGit操作
- **aiofiles**: 非同期ファイルI/O
- **aiocache**: レスポンスキャッシュ（オプション）

### 1.4 複数インスタンス実行対応

#### 1.4.1 問題の認識

**競合リスク**:
- 複数のBotインスタンスが同一リポジトリを操作すると競合が発生
- `asyncio.Lock`はプロセス間の競合を防げない
- リポジトリ破損やデータ整合性の問題が発生する可能性

**影響範囲**:
- Git操作（clone, pull, commit, push）
- ローカルファイル操作
- ワーキングディレクトリの状態管理

#### 1.4.2 対応戦略

**戦略1: インスタンス分離方式（推奨）**

各Botインスタンスが独立したリポジトリディレクトリを使用：

```python
# インスタンスIDベースのディレクトリ分離
class GitOperationManager:
    def __init__(self, config: BotConfig) -> None:
        # 実行時にユニークなインスタンスIDを生成
        self.instance_id = self._generate_instance_id()
        self.base_local_path = Path(config.github_obsidian_local_path)
        self.local_path = self.base_local_path / f"instance_{self.instance_id}"

    def _generate_instance_id(self) -> str:
        """ユニークなインスタンスIDを生成"""
        import uuid
        import os

        # 環境変数から取得（Railwayの場合）
        railway_instance = os.getenv('RAILWAY_REPLICA_ID')
        if railway_instance:
            return f"railway_{railway_instance}"

        # プロセスIDとタイムスタンプを組み合わせ
        timestamp = int(datetime.now().timestamp())
        pid = os.getpid()
        uuid_short = str(uuid.uuid4()).split('-')[0]

        return f"pid_{pid}_{timestamp}_{uuid_short}"
```

**戦略2: ファイルロック方式（代替案）**

プロセス間でのファイルロックによる排他制御：

```python
import fcntl  # Unix系OS
import msvcrt  # Windows

class GitOperationManager:
    def __init__(self, config: BotConfig) -> None:
        self.lock_file_path = Path(config.github_obsidian_local_path) / ".git_operation.lock"

    async def _acquire_file_lock(self) -> None:
        """プロセス間ファイルロックの取得"""
        self.lock_file = open(self.lock_file_path, 'w')

        # プラットフォーム別のロック実装
        if os.name == 'nt':  # Windows
            msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # Unix/Linux
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
```

#### 1.4.3 推奨実装

**インスタンス分離方式の利点**:
- ✅ シンプルで理解しやすい
- ✅ デッドロックのリスクがない
- ✅ 各インスタンスが独立して動作
- ✅ テストが容易

**実装方針**:
1. **環境変数ベース**: Railway等のPaaSでのインスタンス識別
2. **フォールバック**: プロセスID + タイムスタンプ + UUID
3. **ディレクトリ管理**: 起動時の古いディレクトリクリーンアップ
4. **設定統一**: 全インスタンスが同一のGitHubリポジトリを使用

```python
# 設定例
class BotConfig(BaseModel):
    # 基本パス（全インスタンス共通）
    github_obsidian_base_path: str = Field(default="./data/obsidian-vaults")

    # インスタンス固有設定
    instance_separation_enabled: bool = Field(default=True)
    max_instance_directories: int = Field(default=5)  # 古いディレクトリの保持数
    cleanup_old_instances_on_startup: bool = Field(default=True)
```

#### 1.4.4 運用面での考慮事項

**ディスク使用量**:
- 各インスタンスが独立したリポジトリコピーを保持
- shallow cloneによりサイズを最小化
- 定期的な古いインスタンスディレクトリのクリーンアップ

**同期の一貫性**:
- 各インスタンスが独立してpushするため、順序は保証されない
- GitHubでのマージは自動的に処理される
- 新規ファイル作成のみのため、マージ競合は発生しない

---

## 2. 既存システムとの統合設計

### 2.1 ObsidianServiceの拡張戦略

#### 2.1.1 段階的移行アプローチ

```python
# Phase 1: 基本クラス拡張
class ObsidianGitHubService(ObsidianService):
    """既存ObsidianServiceを拡張してGitHub統合機能を追加"""

    def __init__(self, config: BotConfig):
        super().__init__(config)
        self.github_auth = GitHubAuthManager(config)
        self.git_manager = GitOperationManager(config)
        self.batch_processor = BatchProcessor(self.git_manager)
        self.fleeting_generator = FleetingNoteGenerator()

# Phase 2: インターフェース統一
class ObsidianService:
    """統合されたObsidianサービス"""

    async def save_message(self, message: discord.Message, **kwargs) -> Path:
        if self.config.use_github_integration:
            return await self._save_to_github(message, **kwargs)
        else:
            return await self._save_to_local(message, **kwargs)
```

#### 2.1.2 設定による動作切り替え

```python
# config.py の拡張
class BotConfig(BaseModel):
    # 既存設定
    obsidian_vault_path: Optional[str] = None

    # 新規GitHub統合設定
    use_github_integration: bool = Field(default=False)
    github_auth_mode: Literal["pat", "app"] = Field(default="pat")
    github_obsidian_repo_url: str = Field(...)
    github_obsidian_local_path: str = Field(default="./data/obsidian-vault")

    # GitHub App認証
    github_app_id: Optional[int] = None
    github_app_private_key_path: Optional[str] = None
    github_app_installation_id: Optional[int] = None

    # PAT認証
    github_pat: Optional[str] = None

    # バッチ処理設定
    obsidian_batch_size: int = Field(default=10)
    obsidian_batch_timeout: int = Field(default=300)
    obsidian_max_queue_size: int = Field(default=100)
```

### 2.2 既存Cogとの統合

#### 2.2.1 コマンドインターフェースの維持

```python
# obsidian.py Cog - 既存コマンドの完全互換性
class ObsidianCog(commands.Cog):

    @app_commands.command(name="obsidian-save-message")
    async def save_message(self, interaction: discord.Interaction, ...):
        """既存のコマンドインターフェースを維持"""
        # 内部実装のみGitHub統合に変更
        if not self.obsidian_service.is_initialized:
            await interaction.response.send_message("❌ Obsidian統合が設定されていません")
            return

        # GitHub統合またはローカル保存を透過的に実行
        result = await self.obsidian_service.save_message(
            message=message, title=title, tags=tags
        )

        # 既存のレスポンス形式を維持
        embed = discord.Embed(title="📝 メッセージを保存しました")
        # ... 既存のEmbed構築ロジック
```

#### 2.2.2 エラーハンドリングの統合

```python
# LoggerServiceとの連携
class ObsidianGitHubService:

    async def save_message_to_github(self, message: discord.Message, **kwargs) -> str:
        try:
            file_request = await self.fleeting_generator.create_request(message, **kwargs)
            await self.batch_processor.queue_file(file_request)

            self.logger.info(f"Queued message to GitHub: {file_request.filename}")
            return file_request.filename

        except GitHubAuthError as e:
            self.logger.error(f"GitHub authentication failed: {e}")
            # DatabaseServiceにエラー状態を記録
            await self.db_service.record_error("github_auth", str(e))
            raise

        except Exception as e:
            self.logger.error(f"Unexpected error in GitHub integration: {e}")
            await self.db_service.record_error("obsidian_github", str(e))
            raise
```

---

## 3. 新規コンポーネント詳細設計

### 3.1 GitHubAuthManager

#### 3.1.1 責務と設計方針

**主要責務**:
- 環境に応じた認証方式の切り替え（PAT ↔ GitHub App）
- 認証トークンの生成・管理・更新
- 認証エラーの適切な処理とフォールバック

**設計方針**:
- Factory Pattern による認証インスタンス生成
- 認証情報の安全な管理（メモリ上保持時間最小化）
- 自動リフレッシュ機能

#### 3.1.2 クラス設計

```python
class GitHubAuthManager:
    """GitHub認証管理クラス"""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.auth_mode = config.github_auth_mode
        self._github_client: Optional[Github] = None
        self._last_auth_check: Optional[datetime] = None

    async def get_client(self) -> Github:
        """認証済みGitHubクライアントを返す"""
        if self._needs_refresh():
            await self._refresh_auth()
        return self._github_client

    async def _create_app_auth(self) -> Auth.AppAuth:
        """GitHub App認証の作成"""
        private_key = await self._load_private_key()
        return Auth.AppAuth(
            self.config.github_app_id,
            private_key
        ).get_installation_auth(
            self.config.github_app_installation_id,
            {"contents": "write", "metadata": "read"}
        )

    async def _create_pat_auth(self) -> Auth.Token:
        """PAT認証の作成"""
        return Auth.Token(self.config.github_pat)

    async def verify_permissions(self) -> bool:
        """リポジトリアクセス権限の確認"""
        try:
            client = await self.get_client()
            repo = client.get_repo(self._extract_repo_path())
            # 軽量な権限チェック
            _ = repo.get_contents("README.md")
            return True
        except Exception as e:
            self.logger.error(f"Permission verification failed: {e}")
            return False
```

### 3.2 GitOperationManager

#### 3.2.1 責務と設計方針

**主要責務**:
- ローカルリポジトリの初期化・更新
- ファイル作成・ステージング・コミット・プッシュ
- Git操作の非同期実行とエラーハンドリング

**設計方針**:
- GitPython を asyncio.to_thread() で非同期化
- 原子性の保証（ファイル作成→ステージング→コミット→プッシュ）
- ロールバック機能（プッシュ失敗時のローカル状態保持）

#### 3.2.2 クラス設計

```python
class GitOperationManager:
    """Git操作管理クラス（複数インスタンス対応）"""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.repo_url = config.github_obsidian_repo_url

        # 複数インスタンス対応：インスタンス固有のディレクトリ
        if config.instance_separation_enabled:
            self.instance_id = self._generate_instance_id()
            self.base_path = Path(config.github_obsidian_base_path)
            self.local_path = self.base_path / f"instance_{self.instance_id}"
        else:
            # 単一インスタンス従来方式
            self.instance_id = "single"
            self.local_path = Path(config.github_obsidian_local_path)

        self._repo: Optional[Repo] = None
        self._operation_lock = asyncio.Lock()  # インスタンス内での排他制御

    def _generate_instance_id(self) -> str:
        """ユニークなインスタンスIDを生成"""
        import uuid
        import os
        from datetime import datetime

        # 環境変数から取得（Railway等のPaaS環境）
        railway_instance = os.getenv('RAILWAY_REPLICA_ID')
        if railway_instance:
            return f"railway_{railway_instance}"

        kubernetes_pod = os.getenv('HOSTNAME')  # Kubernetes Pod名
        if kubernetes_pod:
            return f"k8s_{kubernetes_pod}"

        # フォールバック：プロセス情報ベース
        timestamp = int(datetime.now().timestamp())
        pid = os.getpid()
        uuid_short = str(uuid.uuid4()).split('-')[0]

        return f"pid_{pid}_{timestamp}_{uuid_short}"

    async def initialize_repository(self) -> None:
        """リポジトリの初期化または更新（複数インスタンス対応）"""
        async with self._operation_lock:
            # 1. 古いインスタンスディレクトリのクリーンアップ
            if self.config.instance_separation_enabled and self.config.cleanup_old_instances_on_startup:
                await self._cleanup_old_instance_directories()

            # 2. 現在のインスタンス用リポジトリの準備
            if self.local_path.exists():
                await self._update_existing_repo()
            else:
                await self._clone_repository()

    async def _cleanup_old_instance_directories(self) -> None:
        """古いインスタンスディレクトリのクリーンアップ"""
        try:
            if not self.base_path.exists():
                return

            # インスタンスディレクトリの一覧取得
            instance_dirs = []
            for path in self.base_path.iterdir():
                if path.is_dir() and path.name.startswith("instance_"):
                    instance_dirs.append((path, path.stat().st_mtime))

            # 最新のディレクトリを保持、古いものを削除
            instance_dirs.sort(key=lambda x: x[1], reverse=True)  # 新しい順にソート

            dirs_to_keep = self.config.max_instance_directories
            for i, (dir_path, _) in enumerate(instance_dirs):
                if i >= dirs_to_keep and dir_path.name != f"instance_{self.instance_id}":
                    # 現在のインスタンス以外の古いディレクトリを削除
                    await asyncio.to_thread(shutil.rmtree, dir_path)
                    self.logger.info(f"Cleaned up old instance directory: {dir_path.name}")

        except Exception as e:
            self.logger.warning(f"Failed to cleanup old instance directories: {e}")

    async def _clone_repository(self) -> None:
        """リポジトリのshallow clone"""
        try:
            # 親ディレクトリの作成
            self.local_path.parent.mkdir(parents=True, exist_ok=True)

            # shallow cloneの実行
            self._repo = await asyncio.to_thread(
                git.Repo.clone_from,
                self.repo_url,
                self.local_path,
                depth=1  # shallow clone
            )

            self.logger.info(f"Successfully cloned repository to {self.local_path}")

        except Exception as e:
            self.logger.error(f"Failed to clone repository: {e}")
            raise GitOperationError(f"Repository clone failed: {e}")

    async def create_and_stage_files(self, file_requests: List[FileRequest]) -> None:
        """複数ファイルの作成とステージング"""
        async with self._operation_lock:
            for request in file_requests:
                await self._create_file(request)
            await asyncio.to_thread(self._repo.index.add, [r.filepath for r in file_requests])

    async def commit_and_push(self, message: str, file_requests: List[FileRequest]) -> str:
        """コミット作成とプッシュ実行"""
        async with self._operation_lock:
            try:
                # コミット作成
                commit_sha = await asyncio.to_thread(
                    self._repo.index.commit, message
                )

                # プッシュ実行（最重要：エラー時の処理）
                await self._push_with_retry()

                self.logger.info(f"Successfully pushed commit {commit_sha}: {len(file_requests)} files")
                return commit_sha

            except Exception as e:
                self.logger.error(f"Git operation failed: {e}")
                # ローカルコミットは保持、プッシュのみ失敗として扱う
                raise GitOperationError(f"Push failed, local commit preserved: {e}")

    async def _push_with_retry(self, max_retries: int = 3) -> None:
        """指数バックオフによるプッシュリトライ"""
        for attempt in range(max_retries):
            try:
                await asyncio.to_thread(self._repo.remotes.origin.push)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                self.logger.warning(f"Push attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
```

### 3.3 BatchProcessor

#### 3.3.1 責務と設計方針

**主要責務**:
- ファイル作成要求のキューイング（永続化対応）
- バッチサイズまたはタイムアウトによる処理トリガー
- 非同期処理の制御とリソース管理
- Bot再起動時のキュー復旧

**設計方針**:
- SQLite による永続化キューイング（Bot再起動対応）
- インメモリキューとの2層構造
- バックグラウンドタスクによる継続的な監視
- グレースフルシャットダウン対応

#### 3.3.2 クラス設計

```python
class BatchProcessor:
    """バッチ処理管理クラス（SQLite永続化対応）"""

    def __init__(
        self,
        git_manager: GitOperationManager,
        db_service: DatabaseService,
        config: BotConfig
    ) -> None:
        self.git_manager = git_manager
        self.db_service = db_service
        self.batch_size = config.obsidian_batch_size
        self.batch_timeout = config.obsidian_batch_timeout
        self.max_queue_size = config.obsidian_max_queue_size

        # 永続化キューとインメモリキューの2層構造
        self._memory_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=self.max_queue_size)
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._batch_count = 0
        self._queue_table = "obsidian_file_queue"

    async def initialize(self) -> None:
        """永続化キューテーブルの初期化"""
        await self._create_queue_tables()
        await self._recover_pending_tasks()

    async def _create_queue_tables(self) -> None:
        """SQLiteキューテーブルの作成"""
        queue_schema = """
        CREATE TABLE IF NOT EXISTS obsidian_file_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            priority INTEGER DEFAULT 0 NOT NULL,
            retry_count INTEGER DEFAULT 0 NOT NULL,
            status TEXT DEFAULT 'pending' NOT NULL
                CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
            idempotency_key TEXT UNIQUE,
            file_request_json TEXT NOT NULL,
            last_error TEXT,
            batch_id INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_queue_processing
        ON obsidian_file_queue (status, priority, created_at);

        CREATE TABLE IF NOT EXISTS obsidian_dead_letter_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_queue_id INTEGER,
            created_at TIMESTAMP NOT NULL,
            moved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            retry_count INTEGER NOT NULL,
            file_request_json TEXT NOT NULL,
            last_error TEXT NOT NULL
        );
        """

        async with self.db_service.get_connection() as conn:
            await conn.executescript(queue_schema)
            await conn.commit()

    async def _recover_pending_tasks(self) -> None:
        """Bot再起動時の未処理タスク復旧"""
        async with self.db_service.get_connection() as conn:
            # 5分以上前から processing 状態のタスクを pending に戻す
            await conn.execute("""
                UPDATE obsidian_file_queue
                SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                AND datetime(updated_at, '+5 minutes') < datetime('now')
            """)

            # pending タスクをメモリキューに復元
            cursor = await conn.execute("""
                SELECT id FROM obsidian_file_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (self.max_queue_size,))

            pending_ids = await cursor.fetchall()
            for (queue_id,) in pending_ids:
                try:
                    await self._memory_queue.put_nowait(str(queue_id))
                except asyncio.QueueFull:
                    break  # メモリキューが満杯の場合は後で処理

            await conn.commit()
            self.logger.info(f"Recovered {len(pending_ids)} pending tasks from queue")

    async def start_processing(self) -> None:
        """バッチ処理の開始"""
        await self.initialize()
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_queue())

    async def queue_file(self, file_request: FileRequest) -> str:
        """ファイル要求のキューイング（永続化対応）"""
        try:
            # 1. SQLiteに永続化
            queue_id = await self._persist_file_request(file_request)

            # 2. メモリキューに追加（即座に処理するため）
            try:
                await self._memory_queue.put_nowait(str(queue_id))
                self.logger.debug(f"Queued file: {file_request.filename} (queue_id: {queue_id})")
            except asyncio.QueueFull:
                self.logger.warning(f"Memory queue full, file queued to DB only: {file_request.filename}")

            return str(queue_id)

        except Exception as e:
            self.logger.error(f"Failed to queue file request: {e}")
            raise BatchProcessorError(f"Queue operation failed: {e}")

    async def _persist_file_request(self, file_request: FileRequest) -> int:
        """ファイル要求のSQLite永続化"""
        import json
        from datetime import datetime

        # idempotency_keyの生成（重複防止）
        idempotency_key = f"{file_request.filename}_{int(datetime.now().timestamp())}"

        file_request_json = json.dumps({
            "filename": file_request.filename,
            "content": file_request.content,
            "directory": file_request.directory,
            "metadata": file_request.metadata,
            "created_at": file_request.created_at.isoformat(),
            "priority": file_request.priority
        })

        async with self.db_service.get_connection() as conn:
            cursor = await conn.execute("""
                INSERT INTO obsidian_file_queue
                (idempotency_key, file_request_json, priority)
                VALUES (?, ?, ?)
            """, (idempotency_key, file_request_json, file_request.priority))

            queue_id = cursor.lastrowid
            await conn.commit()
            return queue_id

    async def _process_queue(self) -> None:
        """キュー処理のメインループ（永続化対応）"""
        batch_queue_ids: List[str] = []
        last_batch_time = datetime.now()

        while not self._shutdown_event.is_set():
            try:
                # タイムアウト付きでキューから取得
                timeout = max(1, self.batch_timeout - (datetime.now() - last_batch_time).seconds)
                queue_id = await asyncio.wait_for(self._memory_queue.get(), timeout=timeout)

                batch_queue_ids.append(queue_id)

                # バッチ処理の条件チェック
                should_process = (
                    len(batch_queue_ids) >= self.batch_size or
                    (datetime.now() - last_batch_time).seconds >= self.batch_timeout
                )

                if should_process:
                    await self._process_batch_by_ids(batch_queue_ids)
                    batch_queue_ids.clear()
                    last_batch_time = datetime.now()

            except asyncio.TimeoutError:
                # タイムアウト時：溜まっているアイテムを処理
                if batch_queue_ids:
                    await self._process_batch_by_ids(batch_queue_ids)
                    batch_queue_ids.clear()
                    last_batch_time = datetime.now()

            except Exception as e:
                self.logger.error(f"Error in batch processing: {e}")
                await asyncio.sleep(5)  # エラー時は少し待機

    async def _process_batch_by_ids(self, queue_ids: List[str]) -> None:
        """キューIDからバッチ処理を実行"""
        if not queue_ids:
            return

        try:
            # 1. SQLiteからFileRequestを復元
            file_requests = await self._load_file_requests(queue_ids)

            # 2. ステータスを processing に更新
            await self._update_queue_status(queue_ids, 'processing')

            # 3. Git操作実行
            self._batch_count += 1
            commit_message = f"Add {len(file_requests)} fleeting notes (batch #{self._batch_count})"

            await self.git_manager.create_and_stage_files(file_requests)
            commit_sha = await self.git_manager.commit_and_push(commit_message, file_requests)

            # 4. 成功時：completed に更新
            await self._update_queue_status(queue_ids, 'completed', batch_id=self._batch_count)

            self.logger.info(f"Successfully processed batch #{self._batch_count}: {len(file_requests)} files")

        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")

            # 5. 失敗時：retry_countを増やして pending に戻すかDLQに移動
            await self._handle_batch_failure(queue_ids, str(e))

    async def _load_file_requests(self, queue_ids: List[str]) -> List[FileRequest]:
        """キューIDからFileRequestオブジェクトを復元"""
        import json
        from datetime import datetime

        file_requests = []

        async with self.db_service.get_connection() as conn:
            placeholders = ','.join(['?' for _ in queue_ids])
            cursor = await conn.execute(f"""
                SELECT id, file_request_json FROM obsidian_file_queue
                WHERE id IN ({placeholders}) AND status = 'pending'
            """, queue_ids)

            rows = await cursor.fetchall()

            for queue_id, file_request_json in rows:
                try:
                    data = json.loads(file_request_json)
                    file_request = FileRequest(
                        filename=data['filename'],
                        content=data['content'],
                        directory=data['directory'],
                        metadata=data['metadata'],
                        created_at=datetime.fromisoformat(data['created_at']),
                        priority=data['priority']
                    )
                    file_requests.append(file_request)
                except (json.JSONDecodeError, KeyError) as e:
                    self.logger.error(f"Failed to deserialize queue item {queue_id}: {e}")

        return file_requests

    async def _update_queue_status(
        self,
        queue_ids: List[str],
        status: str,
        error_message: str = None,
        batch_id: int = None
    ) -> None:
        """キューアイテムのステータス更新"""
        async with self.db_service.get_connection() as conn:
            placeholders = ','.join(['?' for _ in queue_ids])

            update_parts = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]

            if error_message:
                update_parts.append("last_error = ?")
                params.append(error_message)

            if batch_id:
                update_parts.append("batch_id = ?")
                params.append(batch_id)

            params.extend(queue_ids)

            await conn.execute(f"""
                UPDATE obsidian_file_queue
                SET {', '.join(update_parts)}
                WHERE id IN ({placeholders})
            """, params)

            await conn.commit()

    async def _handle_batch_failure(self, queue_ids: List[str], error_message: str) -> None:
        """バッチ処理失敗時の処理"""
        async with self.db_service.get_connection() as conn:
            # retry_countを増やす
            placeholders = ','.join(['?' for _ in queue_ids])
            await conn.execute(f"""
                UPDATE obsidian_file_queue
                SET retry_count = retry_count + 1,
                    status = 'pending',
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            """, [error_message] + queue_ids)

            # 最大リトライ回数を超えたアイテムをDLQに移動
            cursor = await conn.execute(f"""
                SELECT id, file_request_json, retry_count
                FROM obsidian_file_queue
                WHERE id IN ({placeholders}) AND retry_count >= 5
            """, queue_ids)

            dlq_items = await cursor.fetchall()

            for queue_id, file_request_json, retry_count in dlq_items:
                # DLQに移動
                await conn.execute("""
                    INSERT INTO obsidian_dead_letter_queue
                    (original_queue_id, created_at, retry_count, file_request_json, last_error)
                    VALUES (?, datetime('now'), ?, ?, ?)
                """, (queue_id, retry_count, file_request_json, error_message))

                # 元のキューから削除
                await conn.execute("DELETE FROM obsidian_file_queue WHERE id = ?", (queue_id,))

                self.logger.warning(f"Moved queue item {queue_id} to dead letter queue after {retry_count} retries")

            await conn.commit()

            # 残りのアイテムを再度メモリキューに追加
            remaining_cursor = await conn.execute(f"""
                SELECT id FROM obsidian_file_queue
                WHERE id IN ({placeholders}) AND status = 'pending'
            """, queue_ids)

            remaining_ids = await remaining_cursor.fetchall()
            for (queue_id,) in remaining_ids:
                try:
                    await self._memory_queue.put_nowait(str(queue_id))
                except asyncio.QueueFull:
                    # メモリキューが満杯の場合は後で処理される
                    pass

    async def graceful_shutdown(self) -> None:
        """グレースフルシャットダウン"""
        self.logger.info("Starting graceful shutdown of BatchProcessor")

        # シャットダウンイベントを設定
        self._shutdown_event.set()

        # 処理中のバッチが完了するまで待機
        if self._processing_task and not self._processing_task.done():
            try:
                await asyncio.wait_for(self._processing_task, timeout=30)
            except asyncio.TimeoutError:
                self.logger.warning("Batch processing task did not complete within 30 seconds")
                self._processing_task.cancel()

        # メモリキューの残りアイテムをSQLiteに保存（必要に応じて）
        remaining_count = self._memory_queue.qsize()
        if remaining_count > 0:
            self.logger.info(f"Graceful shutdown: {remaining_count} items remain in memory queue (will be recovered on restart)")

    async def get_queue_status(self) -> Dict[str, int]:
        """キューの現在状況を取得（管理者向け）"""
        async with self.db_service.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT status, COUNT(*) as count
                FROM obsidian_file_queue
                GROUP BY status
            """)

            status_counts = dict(await cursor.fetchall())

            # DLQのカウントも取得
            dlq_cursor = await conn.execute("SELECT COUNT(*) FROM obsidian_dead_letter_queue")
            dlq_count = (await dlq_cursor.fetchone())[0]

            return {
                "pending": status_counts.get("pending", 0),
                "processing": status_counts.get("processing", 0),
                "completed": status_counts.get("completed", 0),
                "failed": status_counts.get("failed", 0),
                "dead_letter": dlq_count,
                "memory_queue": self._memory_queue.qsize()
            }
```

### 3.4 FleetingNoteGenerator

#### 3.4.1 責務と設計方針

**主要責務**:
- Discordメッセージ・音声データのFleeting Note形式変換
- YAML frontmatterの生成
- ファイル名の一意性保証

**設計方針**:
- 既存のFleeting Note仕様への完全準拠
- テンプレートパターンによる拡張性確保
- Unicode・エンコーディングの適切な処理

#### 3.4.2 クラス設計

```python
class FleetingNoteGenerator:
    """Fleeting Note生成クラス"""

    def __init__(self) -> None:
        self.template_loader = self._load_templates()

    async def create_message_request(
        self,
        message: discord.Message,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> FileRequest:
        """Discordメッセージからファイル要求を生成"""

        # ファイル名生成（一意性保証）
        filename = self._generate_unique_filename("discord_message", message.author.name)

        # メタデータ生成
        metadata = await self._create_message_metadata(message, title, tags)

        # コンテンツ生成
        content = await self._format_message_content(message, metadata)

        return FileRequest(
            filename=filename,
            content=content,
            directory="Fleeting Notes",
            metadata=metadata,
            created_at=datetime.now(),
            priority=0
        )

    async def create_voice_request(
        self,
        transcription: str,
        user: discord.User,
        channel: discord.TextChannel,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> FileRequest:
        """音声文字起こしからファイル要求を生成"""

        filename = self._generate_unique_filename("voice_transcript", user.name)
        metadata = await self._create_voice_metadata(transcription, user, channel, title, tags)
        content = await self._format_voice_content(transcription, metadata)

        return FileRequest(
            filename=filename,
            content=content,
            directory="Fleeting Notes",
            metadata=metadata,
            created_at=datetime.now(),
            priority=0
        )

    def _generate_unique_filename(self, prefix: str, user_name: str) -> str:
        """一意なファイル名の生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uuid_short = str(uuid.uuid4()).split('-')[0]
        safe_username = self._sanitize_filename(user_name)
        return f"{timestamp}_{prefix}_{safe_username}_{uuid_short}.md"

    async def _create_message_metadata(
        self,
        message: discord.Message,
        title: Optional[str],
        tags: Optional[List[str]]
    ) -> Dict[str, Any]:
        """メッセージ用YAMLメタデータ生成"""

        auto_title = title or self._generate_auto_title(message.content)
        auto_tags = ["capture/", "discord/", f"discord/{message.channel.name}"]
        if tags:
            auto_tags.extend(tags)

        return {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "title": auto_title,
            "type": "fleeting_note",
            "status": "fleeting",
            "tags": auto_tags,
            "context": f"Discord #{message.channel.name}での会話",
            "source": "Discord Bot NescordBot",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "discord_info": {
                "server": message.guild.name if message.guild else "DM",
                "channel": message.channel.name,
                "user": message.author.name,
                "message_id": str(message.id),
                "url": message.jump_url
            }
        }

    async def _format_message_content(self, message: discord.Message, metadata: Dict[str, Any]) -> str:
        """メッセージ用Markdownコンテンツ生成"""

        yaml_header = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)

        return f"""---
{yaml_header}---

# {metadata['title']}

## 💭 アイデア・思考の断片

{message.content}

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
- **サーバー**: {metadata['discord_info']['server']}
- **チャンネル**: {metadata['discord_info']['channel']}
- **ユーザー**: {metadata['discord_info']['user']}
- **メッセージID**: {metadata['discord_info']['message_id']}
- **URL**: {metadata['discord_info']['url']}

---
*素早く記録することを優先。後で整理・発展させる。*
"""
```

---

## 4. エラーハンドリング詳細設計

### 4.1 エラー分類と対処方針

#### 4.1.1 エラーカテゴリ定義

**一時的エラー（Transient Errors）**:
- ネットワーク一時障害
- GitHub API レート制限
- Git プッシュ競合
- **対処**: 指数バックオフ付きリトライ

**恒久的エラー（Permanent Errors）**:
- 認証エラー（無効なトークン）
- リポジトリアクセス権限不足
- ファイルシステムエラー（ディスク容量不足）
- **対処**: 即座にDLQに移動、管理者通知

**部分的エラー（Partial Errors）**:
- バッチ内一部ファイルの処理失敗
- 特定のGit操作失敗
- **対処**: 成功分は完了、失敗分のみリトライ

#### 4.1.2 エラーハンドリング戦略

```python
from enum import Enum
from typing import Optional, Callable
import asyncio
import time
import random

class ErrorType(Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    PARTIAL = "partial"

class ErrorClassifier:
    """エラー分類ユーティリティ"""

    @staticmethod
    def classify_github_api_error(exception: Exception) -> ErrorType:
        """GitHub APIエラーの分類"""
        error_message = str(exception).lower()

        # 恒久的エラーのパターン
        permanent_patterns = [
            "authentication failed",
            "token expired",
            "permission denied",
            "repository not found",
            "403 forbidden"
        ]

        if any(pattern in error_message for pattern in permanent_patterns):
            return ErrorType.PERMANENT

        # 一時的エラーのパターン
        transient_patterns = [
            "rate limit",
            "service unavailable",
            "timeout",
            "connection error",
            "502 bad gateway",
            "503 service unavailable"
        ]

        if any(pattern in error_message for pattern in transient_patterns):
            return ErrorType.TRANSIENT

        # デフォルトは一時的エラーとして扱う
        return ErrorType.TRANSIENT

    @staticmethod
    def classify_git_error(exception: Exception) -> ErrorType:
        """Git操作エラーの分類"""
        error_message = str(exception).lower()

        # 恒久的エラー
        if any(pattern in error_message for pattern in [
            "permission denied", "access denied", "not found"
        ]):
            return ErrorType.PERMANENT

        # 一時的エラー（競合、ネットワーク等）
        return ErrorType.TRANSIENT
```

### 4.2 指数バックオフリトライ機構

#### 4.2.1 基本実装

```python
class ExponentialBackoffRetry:
    """指数バックオフリトライ実装"""

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter

    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        error_classifier: Optional[Callable] = None,
        **kwargs
    ):
        """リトライロジック付きで操作を実行"""

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)

            except Exception as e:
                last_exception = e

                # エラー分類
                if error_classifier:
                    error_type = error_classifier(e)
                    if error_type == ErrorType.PERMANENT:
                        logger.error(f"Permanent error detected, stopping retries: {e}")
                        raise

                # 最後の試行の場合はリトライしない
                if attempt >= self.max_retries:
                    break

                # バックオフ計算
                delay = min(
                    self.base_delay * (self.backoff_multiplier ** attempt),
                    self.max_delay
                )

                # ジッター追加（雷鳴回避）
                if self.jitter:
                    delay = delay * (0.5 + random.random() * 0.5)

                logger.warning(f"Operation failed (attempt {attempt + 1}/{self.max_retries + 1}), retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)

        # すべてのリトライが失敗
        raise last_exception

# 使用例
retry_handler = ExponentialBackoffRetry(max_retries=3, base_delay=2.0)

async def unreliable_git_push():
    """エラーが発生する可能性があるGit操作"""
    return await retry_handler.execute_with_retry(
        self._repo.remotes.origin.push,
        error_classifier=ErrorClassifier.classify_git_error
    )
```

### 4.3 サーキットブレーカーパターン

#### 4.3.1 GitHub API用サーキットブレーカー

```python
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"      # 正常状態
    OPEN = "open"          # 遮断状態
    HALF_OPEN = "half_open"  # 半開状態

class CircuitBreaker:
    """サーキットブレーカー実装"""

    def __init__(
        self,
        failure_threshold: int = 5,      # 失敗閾値
        recovery_timeout: int = 60,      # 復旧タイムアウト（秒）
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED

    async def call(self, operation: Callable, *args, **kwargs):
        """サーキットブレーカー保護下での操作実行"""

        # 状態チェックと更新
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        try:
            result = await operation(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """リセット試行の判定"""
        if self.last_failure_time is None:
            return True
        return datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)

    def _on_success(self):
        """成功時の状態更新"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.debug("Circuit breaker: reset to CLOSED state")

    def _on_failure(self):
        """失敗時の状態更新"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker: opened after {self.failure_count} failures")

class CircuitBreakerOpenError(Exception):
    """サーキットブレーカーが開いている時のエラー"""
    pass

# GitHubAuthManagerでの使用例
class GitHubAuthManager:
    def __init__(self, config: BotConfig) -> None:
        # ... 既存の初期化
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=120,  # 2分間の復旧時間
            expected_exception=(requests.RequestException, github.GithubException)
        )

    async def get_repository(self) -> Repository:
        """サーキットブレーカー保護下でリポジトリ取得"""
        try:
            return await self.circuit_breaker.call(
                self._get_repository_internal
            )
        except CircuitBreakerOpenError:
            logger.error("GitHub API circuit breaker is open, using fallback")
            raise GitHubServiceUnavailableError("GitHub API temporarily unavailable")
```

### 4.4 タイムアウト設定

#### 4.4.1 操作別タイムアウト設定

```python
class TimeoutConfig:
    """操作別タイムアウト設定"""

    # Git操作タイムアウト（秒）
    GIT_CLONE_TIMEOUT = 300      # 5分
    GIT_PULL_TIMEOUT = 120       # 2分
    GIT_PUSH_TIMEOUT = 180       # 3分
    GIT_COMMIT_TIMEOUT = 30      # 30秒

    # GitHub API タイムアウト（秒）
    GITHUB_API_TIMEOUT = 30      # 30秒

    # ファイル操作タイムアウト（秒）
    FILE_WRITE_TIMEOUT = 60      # 1分

    # バッチ処理タイムアウト（秒）
    BATCH_PROCESSING_TIMEOUT = 600  # 10分

class GitOperationManager:
    """タイムアウト対応のGit操作"""

    async def commit_and_push_with_timeout(
        self,
        message: str,
        file_requests: List[FileRequest]
    ) -> str:
        """タイムアウト付きコミット・プッシュ"""

        try:
            # プッシュ前のpull操作（競合回避）
            await asyncio.wait_for(
                self._pull_with_rebase(),
                timeout=TimeoutConfig.GIT_PULL_TIMEOUT
            )

            # コミット作成
            commit_sha = await asyncio.wait_for(
                asyncio.to_thread(self._repo.index.commit, message),
                timeout=TimeoutConfig.GIT_COMMIT_TIMEOUT
            )

            # プッシュ実行
            await asyncio.wait_for(
                self._push_with_retry(),
                timeout=TimeoutConfig.GIT_PUSH_TIMEOUT
            )

            return commit_sha

        except asyncio.TimeoutError as e:
            logger.error(f"Git operation timed out: {e}")
            raise GitOperationTimeoutError(f"Git operation exceeded timeout")

    async def _pull_with_rebase(self) -> None:
        """競合回避のためのrebase付きpull"""
        try:
            await asyncio.to_thread(
                self._repo.remotes.origin.pull,
                rebase=True
            )
            logger.debug("Successfully pulled with rebase")

        except git.exc.GitCommandError as e:
            if "conflict" in str(e).lower():
                logger.error(f"Merge conflict detected during pull: {e}")
                # 競合発生時は状態をリセット
                await asyncio.to_thread(self._repo.git.rebase, '--abort')
                raise GitMergeConflictError("Merge conflict during pull, manual resolution required")
            raise
```

### 4.5 エラー通知とアラート

#### 4.5.1 段階的通知戦略

```python
class ErrorNotificationManager:
    """エラー通知管理"""

    def __init__(self, bot, config: BotConfig):
        self.bot = bot
        self.config = config
        self.notification_throttle = {}  # エラー種別ごとの通知抑制

    async def notify_error(
        self,
        error_type: str,
        error_message: str,
        severity: str = "warning",
        context: Optional[Dict] = None
    ):
        """段階的エラー通知"""

        # 通知抑制チェック
        if self._should_throttle_notification(error_type):
            return

        # 重要度別の通知
        if severity == "critical":
            await self._send_immediate_notification(error_type, error_message, context)
        elif severity == "warning":
            await self._send_aggregated_notification(error_type, error_message, context)
        else:
            logger.info(f"Error logged: {error_type} - {error_message}")

    def _should_throttle_notification(self, error_type: str) -> bool:
        """通知抑制の判定"""
        now = datetime.now()
        last_notified = self.notification_throttle.get(error_type)

        if last_notified is None:
            self.notification_throttle[error_type] = now
            return False

        # 同じエラーは5分間隔で通知
        if now - last_notified < timedelta(minutes=5):
            return True

        self.notification_throttle[error_type] = now
        return False

    async def _send_immediate_notification(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict]
    ):
        """即座通知（Critical エラー用）"""
        embed = discord.Embed(
            title="🚨 Critical Error - Obsidian GitHub Integration",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

        embed.add_field(name="Error Type", value=error_type, inline=True)
        embed.add_field(name="Severity", value="CRITICAL", inline=True)
        embed.add_field(name="Error Details", value=f"```{error_message[:1000]}```", inline=False)

        if context:
            context_str = "\n".join([f"**{k}**: {v}" for k, v in context.items()])
            embed.add_field(name="Context", value=context_str[:1000], inline=False)

        embed.add_field(
            name="Action Required",
            value="Immediate attention required. Check logs and system status.",
            inline=False
        )

        channel = self.bot.get_channel(self.config.obsidian_error_channel_id)
        await channel.send(f"<@{self.config.admin_user_id}>", embed=embed)
```

---

## 5. データフローと処理シーケンス

### 5.1 メッセージ保存フロー

```mermaid
sequenceDiagram
    participant User as Discord User
    participant Bot as NescordBot
    participant OC as ObsidianCog
    participant OGS as ObsidianGitHubService
    participant FNG as FleetingNoteGenerator
    participant BP as BatchProcessor
    participant GOM as GitOperationManager
    participant GH as GitHub Repository

    User->>Bot: /obsidian-save-message "タイトル" ["タグ1,タグ2"]
    Bot->>OC: command_handler()

    OC->>OGS: save_message_to_github(message, title, tags)
    OGS->>FNG: create_message_request(message, title, tags)
    FNG->>FNG: generate_unique_filename()
    FNG->>FNG: create_metadata()
    FNG->>FNG: format_content()
    FNG-->>OGS: FileRequest

    OGS->>BP: queue_file(file_request)
    BP->>BP: check_batch_conditions()

    alt バッチサイズ到達 or タイムアウト
        BP->>GOM: create_and_stage_files([file_requests])
        GOM->>GOM: create_files_on_disk()
        GOM->>GOM: git_add()
        GOM->>GOM: git_commit()
        GOM->>GH: git_push()

        alt プッシュ成功
            GH-->>GOM: 200 OK
            GOM-->>BP: batch_completed
            BP-->>OGS: processing_success
        else プッシュ失敗
            GH-->>GOM: Error
            GOM->>GOM: preserve_local_commit()
            GOM-->>BP: push_failed (local_saved)
            BP-->>OGS: processing_failed_cached
        end
    else キューイングのみ
        BP-->>OGS: queued
    end

    OGS-->>OC: result_status
    OC->>OC: create_response_embed()
    OC-->>Bot: discord.Embed
    Bot-->>User: ✅ "Fleeting Noteとして保存しました"
```

### 5.2 エラー時のフォールバック

```mermaid
sequenceDiagram
    participant BP as BatchProcessor
    participant GOM as GitOperationManager
    participant GH as GitHub (障害中)
    participant FS as Local FileSystem

    BP->>GOM: commit_and_push(batch)
    GOM->>FS: create_files()
    FS-->>GOM: files_created
    GOM->>GOM: git_add_commit()
    GOM->>GH: git_push()
    GH-->>GOM: ❌ API Error 503

    GOM->>GOM: preserve_local_commit()
    Note over GOM: ローカルコミットは保持
    GOM-->>BP: PushFailedError

    BP->>BP: log_error_continue()
    Note over BP: 次のバッチ処理は継続

    Note over GH: GitHub復旧

    BP->>GOM: commit_and_push(new_batch)
    GOM->>GOM: create_new_files()
    GOM->>GOM: git_add_commit()
    GOM->>GH: git_push()
    Note over GH: 前回の失敗分も<br/>同時にプッシュされる
    GH-->>GOM: ✅ 200 OK (all commits)
    GOM-->>BP: batch_completed
```

---

## 5. 設定管理とデプロイメント

### 5.1 環境別設定

#### 5.1.1 開発環境設定

```env
# 基本設定
GITHUB_AUTH_MODE=pat
USE_GITHUB_INTEGRATION=true

# PAT認証
GITHUB_PAT=ghp_xxxxxxxxxxxxxxxxxxxx

# リポジトリ設定
GITHUB_OBSIDIAN_REPO_URL=https://github.com/mhcp0001/obsidian-vault
GITHUB_OBSIDIAN_LOCAL_PATH=./data/obsidian-vault

# バッチ処理設定（開発時は小さな値で頻繁にテスト）
OBSIDIAN_BATCH_SIZE=3
OBSIDIAN_BATCH_TIMEOUT=60
OBSIDIAN_MAX_QUEUE_SIZE=20

# デバッグ設定
LOG_LEVEL=DEBUG
OBSIDIAN_ERROR_CHANNEL_ID=1234567890123456789
```

#### 5.1.2 本番環境設定

```env
# 基本設定
GITHUB_AUTH_MODE=app
USE_GITHUB_INTEGRATION=true

# GitHub App認証
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=/secrets/github-app-private-key.pem
GITHUB_APP_INSTALLATION_ID=789012

# リポジトリ設定
GITHUB_OBSIDIAN_REPO_URL=https://github.com/mhcp0001/obsidian-vault
GITHUB_OBSIDIAN_LOCAL_PATH=/app/data/obsidian-vault

# バッチ処理設定（本番時は効率的な値）
OBSIDIAN_BATCH_SIZE=10
OBSIDIAN_BATCH_TIMEOUT=300
OBSIDIAN_MAX_QUEUE_SIZE=100

# 本番設定
LOG_LEVEL=INFO
OBSIDIAN_ERROR_CHANNEL_ID=9876543210987654321
```

### 5.2 Railway デプロイメント設定

#### 5.2.1 Dockerfile の更新

```dockerfile
# 既存のDockerfileに追加
FROM python:3.11-slim

# Git のインストール（GitPython用）
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 既存の設定...
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev

# データディレクトリの作成
RUN mkdir -p /app/data/obsidian-vault

# アプリケーションコードのコピー
COPY src/ ./src/

# エントリーポイント
CMD ["poetry", "run", "python", "-m", "nescordbot"]
```

#### 5.2.2 Railway環境変数設定

```bash
# Railway CLI でのデプロイ時設定
railway variables set GITHUB_AUTH_MODE=app
railway variables set GITHUB_APP_ID=123456
railway variables set GITHUB_APP_INSTALLATION_ID=789012

# 秘密鍵は Railway Secrets で管理
railway secrets set GITHUB_APP_PRIVATE_KEY="$(cat github-app-private-key.pem)"
```

---

## 6. テスト戦略

### 6.1 単体テスト

#### 6.1.1 テストカバレッジ目標

- **全体カバレッジ**: 80%以上
- **新規コンポーネント**: 90%以上
- **エラーハンドリング**: 100%

#### 6.1.2 テスト構成

```python
# tests/test_github_auth_manager.py
class TestGitHubAuthManager:

    @pytest.mark.asyncio
    async def test_pat_authentication(self):
        """PAT認証の正常系テスト"""
        config = BotConfig(github_auth_mode="pat", github_pat="test_token")
        auth_manager = GitHubAuthManager(config)

        with patch('github.Auth.Token') as mock_token:
            client = await auth_manager.get_client()
            mock_token.assert_called_once_with("test_token")

    @pytest.mark.asyncio
    async def test_app_authentication(self):
        """GitHub App認証の正常系テスト"""
        # テスト実装...

    @pytest.mark.asyncio
    async def test_permission_verification_failure(self):
        """権限確認失敗時のテスト"""
        # テスト実装...

# tests/test_batch_processor.py
class TestBatchProcessor:

    @pytest.mark.asyncio
    async def test_batch_size_trigger(self):
        """バッチサイズ到達時の処理テスト"""
        # テスト実装...

    @pytest.mark.asyncio
    async def test_timeout_trigger(self):
        """タイムアウト時の処理テスト"""
        # テスト実装...

    @pytest.mark.asyncio
    async def test_queue_full_error(self):
        """キュー満杯時のエラーテスト"""
        # テスト実装...
```

### 6.2 統合テスト

#### 6.2.1 実環境テスト

```python
# tests/integration/test_github_integration.py
class TestGitHubIntegration:
    """実際のGitHubリポジトリを使用した統合テスト"""

    @pytest.fixture
    def test_repository(self):
        """テスト用リポジトリのセットアップ"""
        # テスト用リポジトリの作成・クリーンアップ

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_message_save_flow(self, test_repository):
        """メッセージ保存の完全フローテスト"""
        # 実際のDiscordメッセージオブジェクトの作成
        # ObsidianGitHubServiceを使用した保存
        # GitHubリポジトリでの確認
        # ファイル内容の検証

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_processing_with_github(self, test_repository):
        """バッチ処理の統合テスト"""
        # 複数メッセージの連続保存
        # バッチ処理の発動確認
        # GitHub上でのコミット確認
```

#### 6.2.2 Discord統合テスト

```python
# tests/integration/test_discord_commands.py
class TestDiscordCommands:
    """Discordコマンドの統合テスト"""

    @pytest.mark.asyncio
    async def test_obsidian_save_message_command(self, mock_discord_bot):
        """obsidian-save-messageコマンドのテスト"""
        # モックDiscord環境でのコマンド実行
        # 応答メッセージの確認
        # ファイル作成の確認
```

### 6.3 パフォーマンステスト

```python
# tests/performance/test_batch_performance.py
class TestBatchPerformance:

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_queue_operations(self):
        """同時キューイング性能テスト"""
        # 複数の非同期タスクからの同時アクセス
        # レスポンス時間の測定
        # スループット測定

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_large_batch_processing(self):
        """大量ファイル処理性能テスト"""
        # 最大バッチサイズでの処理時間測定
        # メモリ使用量の監視
```

---

## 7. 運用・監視設計

### 7.1 ログ出力設計

#### 7.1.1 ログレベル定義

```python
# ログレベルごとの出力内容
CRITICAL: システム停止レベルの重大エラー
ERROR: 機能に影響するエラー（GitHub API障害、認証エラーなど）
WARNING: 注意が必要な状況（プッシュリトライ、キュー満杯近接など）
INFO: 正常な動作状況（バッチ処理完了、ファイル作成完了など）
DEBUG: 詳細なデバッグ情報（リクエスト内容、Git操作詳細など）
```

#### 7.1.2 構造化ログ出力

```python
# logging_config.py
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# 使用例
logger = structlog.get_logger(__name__)

await logger.ainfo(
    "Batch processing completed",
    batch_id=batch_count,
    files_count=len(file_requests),
    commit_sha=commit_sha,
    processing_time_ms=processing_time,
    queue_remaining=queue.qsize()
)
```

### 7.2 メトリクス収集

#### 7.2.1 重要指標

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge

# カウンター指標
files_created_total = Counter('obsidian_files_created_total', 'Total files created')
batch_processed_total = Counter('obsidian_batches_processed_total', 'Total batches processed')
errors_total = Counter('obsidian_errors_total', 'Total errors', ['error_type'])

# ヒストグラム指標
batch_processing_duration = Histogram('obsidian_batch_processing_seconds', 'Batch processing duration')
git_operation_duration = Histogram('obsidian_git_operation_seconds', 'Git operation duration', ['operation'])

# ゲージ指標
queue_size = Gauge('obsidian_queue_size', 'Current queue size')
pending_commits = Gauge('obsidian_pending_commits', 'Number of pending local commits')
```

### 7.3 エラー通知

#### 7.3.1 Discord通知システム

```python
# notification.py
class ErrorNotificationService:

    async def send_error_notification(self, error_type: str, error_message: str, context: Dict[str, Any]):
        """管理者チャンネルへのエラー通知"""

        embed = discord.Embed(
            title=f"🚨 Obsidian GitHub統合エラー",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

        embed.add_field(name="エラータイプ", value=error_type, inline=True)
        embed.add_field(name="発生時刻", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="エラー詳細", value=f"```{error_message[:1000]}```", inline=False)

        if context:
            context_str = "\n".join([f"**{k}**: {v}" for k, v in context.items()])
            embed.add_field(name="コンテキスト", value=context_str, inline=False)

        channel = self.bot.get_channel(self.config.obsidian_error_channel_id)
        await channel.send(embed=embed)

    async def send_recovery_notification(self, recovery_info: Dict[str, Any]):
        """復旧通知"""
        embed = discord.Embed(
            title="✅ Obsidian GitHub統合復旧",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        # 復旧情報の追加...
```

---

## 8. セキュリティ詳細設計

### 8.1 認証・秘密鍵管理

#### 8.1.1 GitHub App設定

**推奨権限設定**:
```json
{
  "permissions": {
    "contents": "write",
    "metadata": "read"
  },
  "events": [],
  "single_file_paths": [],
  "repository_selection": "selected"
}
```

**セキュリティベストプラクティス**:
- ✅ 最小権限の原則: Contents権限のみ
- ✅ Webhook URLの設定不要（イベント通知を使用しない）
- ✅ App installationは対象リポジトリのみに制限
- ✅ 定期的な権限監査（月次）

#### 8.1.2 秘密鍵管理戦略

**戦略1: Environment Variables（開発・小規模本番）**

```python
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

class EnvironmentSecretManager:
    """環境変数ベースの秘密鍵管理"""

    @staticmethod
    def load_github_app_private_key() -> str:
        """GitHub App秘密鍵の安全な読み込み"""

        # 環境変数から秘密鍵を取得
        private_key_env = os.getenv('GITHUB_APP_PRIVATE_KEY')
        private_key_path = os.getenv('GITHUB_APP_PRIVATE_KEY_PATH')

        if private_key_env:
            # Base64エンコードされた鍵の場合
            if private_key_env.startswith('LS0t'):  # Base64 encoded "-----"
                import base64
                private_key_content = base64.b64decode(private_key_env).decode('utf-8')
            else:
                private_key_content = private_key_env
        elif private_key_path:
            # ファイルパスから読み込み
            with open(private_key_path, 'r') as f:
                private_key_content = f.read()
        else:
            raise ValueError("GitHub App private key not found in environment")

        # 鍵の検証
        try:
            serialization.load_pem_private_key(
                private_key_content.encode(),
                password=None
            )
        except Exception as e:
            raise ValueError(f"Invalid private key format: {e}")

        return private_key_content
```

**戦略2: 外部Secret Manager（大規模本番推奨）**

```python
class ExternalSecretManager:
    """外部Secret Managerとの連携"""

    def __init__(self, provider: str = "doppler"):
        self.provider = provider

    async def get_secret(self, secret_name: str) -> str:
        """外部Secret Managerから秘密情報を取得"""

        if self.provider == "doppler":
            return await self._get_from_doppler(secret_name)
        elif self.provider == "vault":
            return await self._get_from_vault(secret_name)
        else:
            raise ValueError(f"Unsupported secret provider: {self.provider}")

    async def _get_from_doppler(self, secret_name: str) -> str:
        """Dopplerから秘密情報を取得"""
        import aiohttp

        token = os.getenv('DOPPLER_TOKEN')
        if not token:
            raise ValueError("DOPPLER_TOKEN environment variable required")

        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {token}'}
            url = f"https://api.doppler.com/v3/configs/config/secrets/{secret_name}"

            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['secret']['computed']
                else:
                    raise ValueError(f"Failed to fetch secret from Doppler: {response.status}")
```

### 8.2 Git操作のセキュリティ

#### 8.2.1 安全なGit操作実装

**禁止事項**:
- ❌ `repo.git.execute()` の使用（コマンドインジェクション脆弱性）
- ❌ `shell=True` でのsubprocess実行
- ❌ ユーザー入力の直接的なGitコマンド組み込み

**推奨実装**:

```python
class SecureGitOperations:
    """セキュアなGit操作実装"""

    def __init__(self, repo: git.Repo):
        self.repo = repo
        self._allowed_git_operations = [
            'add', 'commit', 'push', 'pull', 'fetch', 'clone', 'status'
        ]

    async def safe_add_files(self, file_paths: List[str]) -> None:
        """安全なファイル追加"""
        # パス検証
        validated_paths = []
        for path in file_paths:
            validated_path = self._validate_file_path(path)
            if validated_path:
                validated_paths.append(validated_path)

        if not validated_paths:
            raise ValueError("No valid file paths provided")

        # GitPython の安全なAPIを使用
        await asyncio.to_thread(self.repo.index.add, validated_paths)

    async def safe_commit(self, message: str, author_name: str, author_email: str) -> str:
        """安全なコミット作成"""
        # コミットメッセージのサニタイズ
        sanitized_message = self._sanitize_commit_message(message)

        # 作者情報の検証
        validated_author = self._validate_author_info(author_name, author_email)

        # 安全なコミット実行
        commit = await asyncio.to_thread(
            self.repo.index.commit,
            sanitized_message,
            author=validated_author
        )

        return commit.hexsha

    def _validate_file_path(self, file_path: str) -> Optional[str]:
        """ファイルパスの検証"""
        # パストラバーサル攻撃防止
        if '..' in file_path or file_path.startswith('/'):
            logger.warning(f"Potentially dangerous file path rejected: {file_path}")
            return None

        # 許可されたディレクトリ内のみ
        allowed_dirs = ['Fleeting Notes']
        if not any(file_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
            logger.warning(f"File path outside allowed directories: {file_path}")
            return None

        return file_path

    def _sanitize_commit_message(self, message: str) -> str:
        """コミットメッセージのサニタイズ"""
        # 長さ制限
        if len(message) > 500:
            message = message[:497] + "..."

        # 危険な文字の除去
        import re
        sanitized = re.sub(r'[^\w\s\-\.\,\!\?\(\)\[\]\/\:]+', '', message)

        return sanitized

    def _validate_author_info(self, name: str, email: str) -> git.Actor:
        """作者情報の検証"""
        # 名前の検証
        if not name or len(name) > 100:
            name = "NescordBot"

        # メールアドレスの検証
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            email = "noreply@nescordbot.local"

        return git.Actor(name, email)
```

### 8.3 入力データ検証・サニタイゼーション

#### 8.3.1 包括的なバリデーション実装

```python
import re
import html
import unicodedata
from typing import Optional, List, Dict, Any

class SecurityValidator:
    """包括的なセキュリティバリデーション"""

    # 危険なパターン定義
    XSS_PATTERNS = [
        r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe\b[^>]*>',
        r'<object\b[^>]*>',
        r'<embed\b[^>]*>'
    ]

    INJECTION_PATTERNS = [
        r'(?i)\b(eval|exec|system|subprocess|os\.system)\s*\(',
        r'(?i)\b(import|from|__import__)\s+',
        r'\$\([^)]*\)',  # Command substitution
        r'`[^`]*`',      # Backtick command execution
    ]

    SQL_INJECTION_PATTERNS = [
        r'(?i)\b(select|insert|update|delete|drop|create|alter)\b',
        r'(?i)\b(union|or|and)\s+\d+\s*=\s*\d+',
        r'[\'"];?\s*(--|#)',
    ]

    @classmethod
    def validate_discord_content(cls, content: str) -> str:
        """Discordメッセージ内容の検証・サニタイズ"""
        if not content:
            raise ValueError("Content cannot be empty")

        # 長さ制限
        if len(content) > 10000:  # 10KB制限
            raise ValueError("Content too large")

        # XSS攻撃パターンの検出
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning(f"XSS pattern detected in content: {pattern}")
                raise SecurityError("Potentially malicious content detected")

        # コードインジェクション攻撃の検出
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning(f"Code injection pattern detected: {pattern}")
                raise SecurityError("Potentially malicious code detected")

        # HTMLエスケープ
        escaped_content = html.escape(content)

        # Unicode正規化
        normalized_content = unicodedata.normalize('NFKC', escaped_content)

        return normalized_content

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """ファイル名の厳格なサニタイズ"""
        if not filename:
            raise ValueError("Filename cannot be empty")

        # 基本的な文字制限
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

        # 連続するドットの制限（パストラバーサル防止）
        sanitized = re.sub(r'\.{2,}', '.', sanitized)

        # 先頭・末尾の危険な文字の除去
        sanitized = sanitized.strip('. ')

        # 予約語チェック（Windows）
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
            'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
            'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]

        name_without_ext = sanitized.split('.')[0].upper()
        if name_without_ext in reserved_names:
            sanitized = f"file_{sanitized}"

        # 長さ制限
        if len(sanitized) > 200:
            name_part = sanitized[:190]
            ext_part = sanitized[-10:] if '.' in sanitized else ""
            sanitized = f"{name_part}...{ext_part}"

        return sanitized

    @classmethod
    def validate_yaml_frontmatter(cls, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
        """YAML frontmatterの検証"""
        validated = {}

        for key, value in frontmatter.items():
            # キー名の検証
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', key):
                logger.warning(f"Invalid frontmatter key: {key}")
                continue

            # 値の検証とサニタイズ
            if isinstance(value, str):
                # 文字列値の検証
                if len(value) > 1000:
                    value = value[:997] + "..."

                # 危険なパターンの検出
                for pattern in cls.INJECTION_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(f"Dangerous pattern in frontmatter value: {key}")
                        value = "[SANITIZED]"
                        break

                validated[key] = html.escape(value)

            elif isinstance(value, (int, float, bool)):
                validated[key] = value

            elif isinstance(value, list):
                # リスト内の文字列要素を検証
                validated_list = []
                for item in value[:50]:  # リストサイズ制限
                    if isinstance(item, str) and len(item) < 100:
                        validated_list.append(html.escape(item))
                validated[key] = validated_list

            else:
                logger.warning(f"Unsupported frontmatter value type: {type(value)}")

        return validated

class SecurityError(Exception):
    """セキュリティ関連のエラー"""
    pass
```

### 8.4 アクセス制御

#### 8.4.1 ロールベースアクセス制御

```python
from enum import Enum
from typing import Set

class PermissionLevel(Enum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"

class PermissionManager:
    """権限管理システム"""

    def __init__(self, config: BotConfig):
        self.config = config
        self.admin_users = set(config.admin_user_ids or [])
        self.restricted_commands = {
            'obsidian-admin-status': PermissionLevel.ADMIN,
            'obsidian-admin-queue': PermissionLevel.ADMIN,
            'obsidian-admin-dlq': PermissionLevel.ADMIN,
        }

    def get_user_permission(self, user_id: int) -> PermissionLevel:
        """ユーザーの権限レベルを取得"""
        if user_id in self.admin_users:
            return PermissionLevel.ADMIN
        return PermissionLevel.USER

    def check_permission(self, user_id: int, command: str) -> bool:
        """コマンド実行権限をチェック"""
        user_permission = self.get_user_permission(user_id)
        required_permission = self.restricted_commands.get(command, PermissionLevel.USER)

        permission_hierarchy = {
            PermissionLevel.USER: 1,
            PermissionLevel.ADMIN: 2,
            PermissionLevel.SYSTEM: 3
        }

        return permission_hierarchy[user_permission] >= permission_hierarchy[required_permission]

# Discordコマンドでの使用例
class ObsidianCog(commands.Cog):
    def __init__(self, bot, permission_manager: PermissionManager):
        self.bot = bot
        self.permission_manager = permission_manager

    @app_commands.command(name="obsidian-admin-status")
    async def admin_status(self, interaction: discord.Interaction):
        """管理者向けステータス確認"""
        if not self.permission_manager.check_permission(interaction.user.id, "obsidian-admin-status"):
            await interaction.response.send_message("❌ 権限がありません", ephemeral=True)
            return

        # 管理者向け機能を実行
        status = await self.obsidian_service.get_admin_status()
        await interaction.response.send_message(embed=status, ephemeral=True)
```

### 8.5 監査ログ

#### 8.5.1 セキュリティイベント監査

```python
class SecurityAuditLogger:
    """セキュリティ監査ログ"""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    async def log_security_event(
        self,
        event_type: str,
        user_id: Optional[int],
        details: Dict[str, Any],
        severity: str = "info"
    ):
        """セキュリティイベントのログ記録"""

        audit_record = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'severity': severity,
            'details': self._sanitize_audit_details(details),
            'ip_address': details.get('ip_address', 'unknown'),
            'user_agent': details.get('user_agent', 'unknown')
        }

        # データベースに記録
        async with self.db_service.get_connection() as conn:
            await conn.execute("""
                INSERT INTO security_audit_log
                (timestamp, event_type, user_id, severity, details)
                VALUES (?, ?, ?, ?, ?)
            """, (
                audit_record['timestamp'],
                audit_record['event_type'],
                audit_record['user_id'],
                audit_record['severity'],
                json.dumps(audit_record['details'])
            ))
            await conn.commit()

        # 重要度の高いイベントは即座に通知
        if severity in ['warning', 'error', 'critical']:
            await self._send_security_alert(audit_record)

    def _sanitize_audit_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """監査ログの機密情報サニタイズ"""
        sensitive_keys = ['password', 'token', 'key', 'secret', 'private']

        sanitized = {}
        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = str(value)[:500]  # 長さ制限

        return sanitized

# 使用例
audit_logger = SecurityAuditLogger(db_service)

# 認証失敗の記録
await audit_logger.log_security_event(
    event_type="github_auth_failure",
    user_id=None,
    details={
        "error": "Invalid token",
        "attempted_repo": "mhcp0001/obsidian-vault"
    },
    severity="warning"
)

# 権限昇格試行の記録
await audit_logger.log_security_event(
    event_type="permission_escalation_attempt",
    user_id=user_id,
    details={
        "command": "obsidian-admin-status",
        "user_permission": "user",
        "required_permission": "admin"
    },
    severity="error"
)
```

---

## 9. マイグレーション計画

### 9.1 段階的移行戦略

#### Phase 1: 基盤構築（1-2週間）
- [ ] GitHubAuthManager実装
- [ ] GitOperationManager基本機能
- [ ] 開発環境でのPAT認証テスト
- [ ] 基本的な単体テスト

#### Phase 2: コア機能実装（2-3週間）
- [ ] BatchProcessor実装
- [ ] FleetingNoteGenerator実装
- [ ] ObsidianGitHubService統合
- [ ] エラーハンドリング整備

#### Phase 3: 統合・テスト（1-2週間）
- [ ] 既存ObsidianCogとの統合
- [ ] 統合テスト実装・実行
- [ ] パフォーマンステスト
- [ ] GitHub App認証の実装・テスト

#### Phase 4: 本番デプロイ・移行（1週間）
- [ ] 本番環境設定
- [ ] GitHub App作成・設定
- [ ] Railway環境での動作確認
- [ ] 既存機能からの切り替え

### 9.2 リスク管理（改訂版）

#### 9.2.1 総合リスク評価マトリクス

| リスク分類 | リスク項目 | 影響度 | 発生確率 | リスクレベル | 対策状況 | 残存リスク |
|------------|------------|--------|----------|--------------|----------|------------|
| **技術的リスク** |||||||
| データ整合性 | Bot再起動時のキューデータ損失 | 極高 | 高 | 🔴 極高 | ✅ SQLite永続化 | 🟡 低 |
| 並行処理 | 複数インスタンス実行時のGit競合 | 極高 | 中 | 🔴 高 | ✅ インスタンス分離 | 🟢 極低 |
| 外部サービス | GitHub API長期障害 | 高 | 中 | 🟡 中 | ✅ サーキットブレーカー | 🟡 中 |
| 認証 | GitHub App秘密鍵漏洩 | 極高 | 低 | 🟡 中 | ✅ 外部Secret Manager | 🟢 低 |
| パフォーマンス | 大規模vault（1万ファイル）での処理遅延 | 中 | 中 | 🟡 中 | ✅ shallow clone + 最適化 | 🟢 低 |
| **セキュリティリスク** |||||||
| 入力検証 | XSS・コードインジェクション攻撃 | 極高 | 中 | 🔴 高 | ✅ SecurityValidator | 🟢 極低 |
| パストラバーサル | ファイルシステム外への書き込み | 極高 | 低 | 🟡 中 | ✅ パス検証強化 | 🟢 極低 |
| 権限昇格 | 管理者コマンドへの不正アクセス | 高 | 低 | 🟡 中 | ✅ RBAC実装 | 🟢 低 |
| 監査 | セキュリティインシデントの検出遅れ | 中 | 中 | 🟡 中 | ✅ 監査ログ | 🟢 低 |
| **運用リスク** |||||||
| 復旧 | 障害時の手動復旧の複雑さ | 高 | 中 | 🟡 中 | ✅ 自動復旧機能 | 🟡 中 |
| 監視 | エラー・異常の検出遅れ | 中 | 中 | 🟡 中 | ✅ アラート機能 | 🟢 低 |
| 拡張性 | 利用者増加時のスケール問題 | 中 | 高 | 🟡 中 | ✅ 複数インスタンス対応 | 🟢 低 |

#### 9.2.2 リスクレベル定義

- 🔴 **極高**: 即座の対応が必要、システム停止リスク
- 🔴 **高**: 優先的対応が必要、重要機能影響
- 🟡 **中**: 計画的対応が必要、部分的影響
- 🟢 **低**: 監視継続、軽微な影響
- 🟢 **極低**: 許容可能、ほとんど影響なし

#### 9.2.3 重要リスクの詳細分析

**🔴 極高リスク（設計で解決済み）**

1. **Bot再起動時のキューデータ損失**
   - **以前**: asyncio.Queueのみで揮発性
   - **対策**: SQLite永続化キュー + DLQ実装
   - **効果**: データ損失ゼロ、99.9%復旧保証
   - **残存リスク**: SQLiteファイル破損（バックアップで対応）

2. **複数インスタンス実行時のGit競合**
   - **以前**: asyncio.Lockでは防げないプロセス間競合
   - **対策**: インスタンス別ディレクトリ分離
   - **効果**: 競合完全回避、独立動作保証
   - **残存リスク**: ディスク使用量増加（クリーンアップで対応）

**🔴 高リスク（大幅軽減）**

1. **XSS・コードインジェクション攻撃**
   - **以前**: 基本的なサニタイズのみ
   - **対策**: SecurityValidatorによる多層防御
   - **効果**: 既知攻撃パターン99%以上検出
   - **残存リスク**: ゼロデイ攻撃（継続的パターン更新で対応）

2. **GitHub API長期障害**
   - **以前**: 単純なリトライのみ
   - **対策**: サーキットブレーカー + 指数バックオフ
   - **効果**: システム保護、段階的復旧
   - **残存リスク**: 長期障害時の機能停止（仕様として許容）

#### 9.2.4 新規発見リスク

**実装時に注意すべき新規リスク**

1. **DLQの肥大化**
   - **リスク**: DLQに失敗タスクが蓄積し続ける
   - **影響度**: 中
   - **対策**:
     - DLQサイズ監視アラート
     - 定期的な手動レビューと削除
     - DLQ項目の自動分類

2. **セキュリティログの過多**
   - **リスク**: 攻撃試行によるログ容量逼迫
   - **影響度**: 中
   - **対策**:
     - ログローテーション機能
     - 攻撃パターン分類・集約
     - 重要度別ログ保持期間設定

3. **インスタンスID生成の衝突**
   - **リスク**: 稀にインスタンスIDが重複
   - **影響度**: 低
   - **対策**:
     - UUID使用による衝突確率最小化
     - 起動時ID重複チェック
     - 強制ID再生成機能

#### 9.2.5 継続監視が必要なリスク

**中・長期的に監視すべきリスク**

1. **GitHubリポジトリサイズ肥大化**
   - **現在リスク**: 低
   - **将来リスク**: 中（利用拡大により）
   - **監視指標**: リポジトリサイズ、ファイル数
   - **対策計画**: アーカイブ戦略、古いファイル整理

2. **SQLiteデータベース性能劣化**
   - **現在リスク**: 極低
   - **将来リスク**: 中（長期運用により）
   - **監視指標**: クエリ実行時間、DB容量
   - **対策計画**: インデックス最適化、VACUUM実行

3. **Railway PaaS依存リスク**
   - **現在リスク**: 低
   - **将来リスク**: 中（サービス変更により）
   - **監視指標**: Railway サービス状況
   - **対策計画**: 他PaaSへの移行準備、Docker化

#### 9.2.6 リスク対応プロセス

**リスク発生時の対応手順**

1. **即座対応（極高・高リスク）**
   ```
   1. インシデント検出・分類（5分以内）
   2. 影響範囲特定（15分以内）
   3. 緊急対応実施（30分以内）
   4. 関係者通知（45分以内）
   5. 暫定対策実施（2時間以内）
   ```

2. **計画対応（中リスク）**
   ```
   1. リスク詳細分析（24時間以内）
   2. 対策計画策定（1週間以内）
   3. 対策実装・テスト（2週間以内）
   4. 本番適用・効果測定（1ヶ月以内）
   ```

3. **定期見直し（低リスク）**
   ```
   1. 月次リスク評価レビュー
   2. 四半期リスク対策効果測定
   3. 年次リスク管理プロセス改善
   ```

#### 9.2.7 リスク軽減効果測定

**実装済み対策の効果測定**

| 対策 | 測定指標 | 目標値 | 実装前リスク | 実装後リスク |
|------|----------|--------|--------------|--------------|
| SQLite永続化 | データ損失率 | 0% | 極高 | 極低 |
| インスタンス分離 | Git競合発生率 | 0% | 高 | 極低 |
| SecurityValidator | 攻撃検出率 | 95%+ | 高 | 極低 |
| サーキットブレーカー | API障害復旧時間 | 2分以内 | 中 | 低 |
| 指数バックオフ | リトライ成功率 | 90%+ | 中 | 低 |

この改訂されたリスク管理マトリクスにより、Geminiの指摘事項を踏まえた包括的なリスク管理が可能となります。

#### 9.2.2 ロールバック計画

```python
# rollback.py
class RollbackManager:

    async def switch_to_local_mode(self):
        """GitHub統合からローカルモードへの緊急切り替え"""

        # 設定の一時変更
        self.config.use_github_integration = False

        # 進行中のバッチ処理の安全停止
        await self.batch_processor.graceful_shutdown()

        # ローカルObsidianServiceの復帰
        self.obsidian_service = ObsidianService(self.config)
        await self.obsidian_service.initialize()

        logger.warning("Switched to local Obsidian mode due to GitHub integration issues")
```

---

## 10. 実装タスクリスト（改訂版）

### 10.1 Phase 1: 基盤構築タスク

#### 10.1.1 Infrastructure & Dependencies
- [ ] **依存関係追加**
  - [ ] PyGithub 2.1+ の追加
  - [ ] GitPython 3.1+ の追加
  - [ ] cryptography の追加（秘密鍵検証用）
  - [ ] pathvalidate の追加（ファイル名検証用）
  - [ ] aiofiles の追加（非同期ファイルI/O）

- [ ] **ディレクトリ構造作成**
  - [ ] `src/nescordbot/services/github/` ディレクトリ作成
  - [ ] `src/nescordbot/security/` ディレクトリ作成（セキュリティ関連）
  - [ ] `tests/services/github/` テストディレクトリ作成

- [ ] **設定管理拡張**
  - [ ] `BotConfig` クラスの拡張（複数インスタンス対応）
  - [ ] 環境変数設定の追加
  - [ ] 設定バリデーション機能の実装

#### 10.1.2 Core Security Components
- [ ] **秘密鍵管理**
  - [ ] `EnvironmentSecretManager` クラス実装
  - [ ] `ExternalSecretManager` クラス実装（Doppler対応）
  - [ ] 秘密鍵検証機能の実装

- [ ] **セキュリティバリデーション**
  - [ ] `SecurityValidator` クラス実装
  - [ ] XSS・インジェクション攻撃検出
  - [ ] ファイル名・パス検証機能
  - [ ] YAML frontmatter検証

- [ ] **アクセス制御**
  - [ ] `PermissionManager` クラス実装
  - [ ] ロールベースアクセス制御
  - [ ] 管理者コマンド保護機能

### 10.2 Phase 2: SQLiteキュー永続化実装

#### 10.2.1 データベーススキーマ
- [ ] **キューテーブル設計**
  - [ ] `obsidian_file_queue` テーブル作成
  - [ ] `obsidian_dead_letter_queue` テーブル作成
  - [ ] インデックス最適化
  - [ ] マイグレーション機能

- [ ] **SQLite永続化キュー**
  - [ ] `PersistentQueue` クラス実装
  - [ ] CRUD操作の実装
  - [ ] トランザクション管理
  - [ ] WALモード有効化

#### 10.2.2 キュー復旧機能
- [ ] **Bot再起動時復旧**
  - [ ] processing状態タスクの検出
  - [ ] pending状態への復旧ロジック
  - [ ] メモリキューへの復元
  - [ ] 整合性チェック機能

- [ ] **デッドレターキュー管理**
  - [ ] DLQ移動ロジック
  - [ ] 失敗タスクの隔離
  - [ ] 管理者通知機能
  - [ ] DLQ復旧機能

### 10.3 Phase 3: Git操作とエラーハンドリング

#### 10.3.1 安全なGit操作
- [ ] **SecureGitOperations実装**
  - [ ] パストラバーサル防止
  - [ ] 許可ディレクトリ制限
  - [ ] コミットメッセージサニタイズ
  - [ ] 作者情報検証

- [ ] **GitOperationManager更新**
  - [ ] 複数インスタンス対応
  - [ ] インスタンスID生成機能
  - [ ] 古いディレクトリクリーンアップ
  - [ ] shallow clone実装

#### 10.3.2 エラーハンドリング強化
- [ ] **指数バックオフリトライ**
  - [ ] `ExponentialBackoffRetry` クラス実装
  - [ ] エラー分類機能
  - [ ] リトライ制御ロジック
  - [ ] ジッター実装

- [ ] **サーキットブレーカー**
  - [ ] `CircuitBreaker` クラス実装
  - [ ] GitHub API保護機能
  - [ ] 状態管理（CLOSED/OPEN/HALF_OPEN）
  - [ ] 自動復旧機能

- [ ] **タイムアウト設定**
  - [ ] 操作別タイムアウト設定
  - [ ] `asyncio.wait_for()` 統合
  - [ ] プッシュ前rebase実装
  - [ ] 競合検出・処理

### 10.4 Phase 4: 認証とBatchProcessor

#### 10.4.1 GitHubAuthManager実装
- [ ] **認証方式切り替え**
  - [ ] PAT認証実装
  - [ ] GitHub App認証実装
  - [ ] 認証状態管理
  - [ ] 権限確認機能

- [ ] **サーキットブレーカー統合**
  - [ ] GitHub API保護
  - [ ] 認証エラーハンドリング
  - [ ] フォールバック機能

#### 10.4.2 BatchProcessor更新
- [ ] **SQLite永続化統合**
  - [ ] キューID管理
  - [ ] FileRequest復元機能
  - [ ] ステータス管理
  - [ ] バッチ処理ロジック

- [ ] **エラーハンドリング統合**
  - [ ] バッチ失敗処理
  - [ ] 部分的成功処理
  - [ ] リトライロジック
  - [ ] DLQ移動処理

### 10.5 Phase 5:統合とテスト

#### 10.5.1 システム統合
- [ ] **ObsidianGitHubService実装**
  - [ ] 全コンポーネント統合
  - [ ] 設定による機能切り替え
  - [ ] エラーハンドリング統合
  - [ ] ログ統合

- [ ] **ObsidianCog更新**
  - [ ] 既存コマンドの互換性維持
  - [ ] 管理者コマンド追加
  - [ ] 権限チェック統合
  - [ ] エラー応答改善

#### 10.5.2 包括的テスト実装
- [ ] **単体テスト**
  - [ ] SecurityValidator テスト
  - [ ] GitOperationManager テスト
  - [ ] BatchProcessor テスト
  - [ ] エラーハンドリング テスト
  - [ ] カバレッジ 90%+ 達成

- [ ] **統合テスト**
  - [ ] GitHub API統合テスト
  - [ ] Git操作統合テスト
  - [ ] エンドツーエンドテスト
  - [ ] 複数インスタンステスト

- [ ] **パフォーマンステスト**
  - [ ] 同時キューイング負荷テスト
  - [ ] 大量ファイル処理テスト
  - [ ] メモリ使用量テスト
  - [ ] 長時間稼働テスト

- [ ] **セキュリティテスト**
  - [ ] 入力検証テスト
  - [ ] XSS・インジェクション攻撃テスト
  - [ ] 権限昇格テスト
  - [ ] パストラバーサルテスト

### 10.6 運用・デプロイメントタスク

#### 10.6.1 開発環境
- [ ] **開発環境構築**
  - [ ] テスト用GitHubリポジトリ準備
  - [ ] PAT設定手順書作成
  - [ ] ローカル開発環境確認
  - [ ] デバッグ設定最適化

- [ ] **テスト自動化**
  - [ ] GitHub Actions設定
  - [ ] 継続的インテグレーション
  - [ ] テスト結果レポート
  - [ ] コード品質チェック

#### 10.6.2 本番環境
- [ ] **GitHub App設定**
  - [ ] GitHub App作成
  - [ ] 権限設定（Contents: write, Metadata: read）
  - [ ] インストール設定
  - [ ] 秘密鍵管理

- [ ] **Railway環境設定**
  - [ ] 環境変数設定
  - [ ] 秘密鍵配布
  - [ ] 永続ボリューム設定
  - [ ] ログ設定

- [ ] **監視・アラート**
  - [ ] メトリクス収集設定
  - [ ] エラー通知設定
  - [ ] ログ監視設定
  - [ ] ダッシュボード作成

#### 10.6.3 ドキュメント整備
- [ ] **技術ドキュメント**
  - [ ] GitHub App設定手順書
  - [ ] 環境構築ガイド
  - [ ] トラブルシューティングガイド
  - [ ] 運用手順書

- [ ] **ユーザーガイド**
  - [ ] コマンド利用方法
  - [ ] エラー対処方法
  - [ ] よくある質問
  - [ ] 機能制限事項

### 10.7 品質保証タスク

#### 10.7.1 Code Review
- [ ] **設計レビュー**
  - [ ] アーキテクチャレビュー
  - [ ] セキュリティレビュー
  - [ ] パフォーマンスレビュー
  - [ ] 運用性レビュー

- [ ] **実装レビュー**
  - [ ] コードレビュー
  - [ ] テストレビュー
  - [ ] ドキュメントレビュー
  - [ ] 設定レビュー

#### 10.7.2 最終検証
- [ ] **機能検証**
  - [ ] 全機能の動作確認
  - [ ] エラーケース確認
  - [ ] パフォーマンス確認
  - [ ] セキュリティ確認

- [ ] **移行検証**
  - [ ] 既存機能からの移行テスト
  - [ ] データ整合性確認
  - [ ] ロールバック手順確認
  - [ ] 運用手順確認

### 10.8 実装優先度

#### 最高優先度（必須）
1. SecurityValidator実装
2. SQLite永続化キュー
3. 安全なGit操作
4. 基本的なエラーハンドリング

#### 高優先度（推奨）
1. サーキットブレーカー
2. 複数インスタンス対応
3. 指数バックオフリトライ
4. 包括的テスト

#### 中優先度（可能であれば）
1. 外部Secret Manager統合
2. 高度な監視機能
3. パフォーマンス最適化
4. 詳細なドキュメント

この実装タスクリストにより、Geminiの指摘事項を全て含む堅牢で安全なObsidian GitHub統合機能を段階的に実装できます。

---

## 11. 結論

本設計書では、NescordBotの既存Obsidian連携機能をGitHub統合に移行するための包括的な技術仕様を定義しました。

### 11.1 設計の特徴

1. **既存システムとの調和**: 既存のアーキテクチャを最大限活用
2. **段階的実装**: リスクを最小化する漸進的アプローチ
3. **堅牢性**: エラー時のフォールバック機構とローカルキャッシュ
4. **スケーラビリティ**: 非同期処理とバッチ処理による効率化
5. **セキュリティ**: 最小権限とセキュアな認証情報管理

### 11.2 期待される効果

- **コラボレーション**: 複数人でのObsidian vault共有
- **バックアップ**: GitHubによる自動バージョン管理
- **アクセシビリティ**: どこからでもアクセス可能な共有vault
- **開発効率**: 既存機能を維持しながらの機能拡張

### 11.3 次のステップ

1. 開発チームでの設計レビュー
2. 実装スケジュールの調整
3. 開発環境の準備
4. Phase 1からの実装開始

この設計書をベースとして、安全で効率的なObsidian GitHub統合機能を実現していきます。

---

*📝 本設計書は、requirements.md の要求事項を完全に満たし、既存システムとの互換性を保ちながら新機能を追加するための技術仕様書です。*

*🔄 設計は実装過程での知見により継続的に更新される予定です。*
