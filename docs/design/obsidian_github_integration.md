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
    """Git操作管理クラス"""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.repo_url = config.github_obsidian_repo_url
        self.local_path = Path(config.github_obsidian_local_path)
        self._repo: Optional[Repo] = None
        self._operation_lock = asyncio.Lock()

    async def initialize_repository(self) -> None:
        """リポジトリの初期化または更新"""
        async with self._operation_lock:
            if self.local_path.exists():
                await self._update_existing_repo()
            else:
                await self._clone_repository()

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
- ファイル作成要求のキューイング
- バッチサイズまたはタイムアウトによる処理トリガー
- 非同期処理の制御とリソース管理

**設計方針**:
- asyncio.Queue によるスレッドセーフなキューイング
- バックグラウンドタスクによる継続的な監視
- グレースフルシャットダウン対応

#### 3.3.2 クラス設計

```python
class BatchProcessor:
    """バッチ処理管理クラス"""

    def __init__(self, git_manager: GitOperationManager, config: BotConfig) -> None:
        self.git_manager = git_manager
        self.batch_size = config.obsidian_batch_size
        self.batch_timeout = config.obsidian_batch_timeout
        self.max_queue_size = config.obsidian_max_queue_size

        self._queue: asyncio.Queue[FileRequest] = asyncio.Queue(maxsize=self.max_queue_size)
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._batch_count = 0

    async def start_processing(self) -> None:
        """バッチ処理の開始"""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_queue())

    async def queue_file(self, file_request: FileRequest) -> None:
        """ファイル要求のキューイング"""
        try:
            await self._queue.put(file_request)
            self.logger.debug(f"Queued file: {file_request.filename} (queue size: {self._queue.qsize()})")
        except asyncio.QueueFull:
            raise BatchProcessorError("Queue is full, cannot accept new requests")

    async def _process_queue(self) -> None:
        """キュー処理のメインループ"""
        batch: List[FileRequest] = []
        last_batch_time = datetime.now()

        while not self._shutdown_event.is_set():
            try:
                # タイムアウト付きでキューから取得
                timeout = max(1, self.batch_timeout - (datetime.now() - last_batch_time).seconds)
                file_request = await asyncio.wait_for(self._queue.get(), timeout=timeout)

                batch.append(file_request)

                # バッチ処理の条件チェック
                should_process = (
                    len(batch) >= self.batch_size or
                    (datetime.now() - last_batch_time).seconds >= self.batch_timeout
                )

                if should_process:
                    await self._process_batch(batch)
                    batch.clear()
                    last_batch_time = datetime.now()

            except asyncio.TimeoutError:
                # タイムアウト時：溜まっているアイテムを処理
                if batch:
                    await self._process_batch(batch)
                    batch.clear()
                    last_batch_time = datetime.now()

            except Exception as e:
                self.logger.error(f"Error in batch processing: {e}")
                await asyncio.sleep(5)  # エラー時は少し待機

    async def _process_batch(self, batch: List[FileRequest]) -> None:
        """バッチの実際の処理"""
        if not batch:
            return

        self._batch_count += 1
        commit_message = f"Add {len(batch)} fleeting notes (batch #{self._batch_count})"

        try:
            await self.git_manager.create_and_stage_files(batch)
            await self.git_manager.commit_and_push(commit_message, batch)

            self.logger.info(f"Successfully processed batch #{self._batch_count}: {len(batch)} files")

        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")
            # エラー発生時も次のバッチは処理続行
            # ローカルコミットは保持されているため、次回のプッシュで同期される
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

## 4. データフローと処理シーケンス

### 4.1 メッセージ保存フロー

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

### 4.2 エラー時のフォールバック

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

## 8. セキュリティ設計

### 8.1 認証情報管理

#### 8.1.1 GitHub App設定

**推奨権限設定**:
```json
{
  "permissions": {
    "contents": "write",
    "metadata": "read"
  },
  "events": []
}
```

**セキュリティベストプラクティス**:
- 最小権限の原則: Contents権限のみ
- Webhook URLの設定不要（イベント通知を使用しない）
- App installationは対象リポジトリのみに制限

#### 8.1.2 秘密鍵管理

```python
# secret_manager.py
class SecretManager:

    @staticmethod
    async def load_private_key(key_path: str) -> str:
        """秘密鍵の安全な読み込み"""
        try:
            async with aiofiles.open(key_path, 'r') as f:
                key_content = await f.read()

            # 鍵の形式検証
            if not key_content.startswith('-----BEGIN PRIVATE KEY-----'):
                raise ValueError("Invalid private key format")

            return key_content

        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise AuthenticationError("Private key loading failed")

    @staticmethod
    def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """ログ出力時の機密情報マスキング"""
        sensitive_keys = ['token', 'key', 'secret', 'password', 'auth']

        sanitized = {}
        for k, v in data.items():
            if any(sensitive in k.lower() for sensitive in sensitive_keys):
                sanitized[k] = '***REDACTED***'
            else:
                sanitized[k] = v

        return sanitized
```

### 8.2 データ保護

#### 8.2.1 ファイル内容の検証

```python
# content_validator.py
class ContentValidator:

    @staticmethod
    def validate_file_content(content: str) -> bool:
        """ファイル内容の安全性検証"""

        # 基本的な検証
        if len(content) > 1_000_000:  # 1MB制限
            raise ValueError("File content too large")

        # 悪意のあるパターンの検出
        malicious_patterns = [
            r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>',  # JavaScript
            r'(?i)\b(eval|exec|system|subprocess)\s*\(',  # 危険な関数呼び出し
        ]

        for pattern in malicious_patterns:
            if re.search(pattern, content):
                raise SecurityError("Potentially malicious content detected")

        return True

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """ファイル名のサニタイズ"""
        # 危険な文字の除去
        safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)

        # 長さ制限
        if len(safe_chars) > 100:
            safe_chars = safe_chars[:97] + "..."

        return safe_chars
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

### 9.2 リスク管理

#### 9.2.1 主要リスク

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|----------|------|
| GitHub API障害 | 高 | 中 | ローカルキャッシュ、自動復旧機能 |
| 認証エラー | 高 | 低 | PAT フォールバック、詳細エラーログ |
| Git競合 | 中 | 低 | 新規ファイルのみ、一意名保証 |
| パフォーマンス劣化 | 中 | 中 | 非同期処理、バッチ処理最適化 |

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

## 10. 実装タスクリスト

### 10.1 開発タスク

#### Infrastructure タスク
- [ ] `src/nescordbot/services/github/` ディレクトリ作成
- [ ] PyGithub, GitPython依存関係追加
- [ ] 既存BotConfigクラスの拡張
- [ ] ログ設定の更新

#### Core Components
- [ ] `GitHubAuthManager` クラス実装
- [ ] `GitOperationManager` クラス実装
- [ ] `BatchProcessor` クラス実装
- [ ] `FleetingNoteGenerator` クラス実装

#### Integration
- [ ] `ObsidianGitHubService` クラス実装
- [ ] 既存`ObsidianCog`の更新
- [ ] エラーハンドリングの統合
- [ ] 設定による機能切り替え実装

#### Testing
- [ ] 単体テストの実装
- [ ] 統合テストの実装
- [ ] パフォーマンステストの実装
- [ ] GitHub App認証テスト

### 10.2 運用タスク

#### Development Environment
- [ ] 開発用GitHub Personal Access Token設定
- [ ] テスト用リポジトリの準備
- [ ] ローカル開発環境の動作確認

#### Production Environment
- [ ] GitHub App作成・設定
- [ ] Railway環境変数設定
- [ ] 秘密鍵の安全な配布
- [ ] 本番動作確認

#### Documentation
- [ ] GitHub App設定手順書
- [ ] トラブルシューティングガイド
- [ ] 運用手順書
- [ ] ユーザー向け利用ガイド

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
