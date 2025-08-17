# NescordBot コードベース・アーキテクチャ

## 全体アーキテクチャ

### レイヤー構造
```
Presentation Layer (Discord Interface)
├── discord.py Commands & Events
├── Slash Commands (/help, /status, /ping)
└── Voice Message Handlers

Application Layer (Business Logic)
├── Cogs (Command Groups)
│   ├── GeneralCog - 基本コマンド
│   ├── VoiceCog - 音声処理
│   ├── AdminCog - 管理機能
│   ├── GitHubCog - GitHub統合
│   └── ObsidianCog - Obsidian連携
└── Services (External Integration)
    ├── DatabaseService - データ永続化
    ├── GitHubService - GitHub API
    └── ObsidianService - Vault操作

Infrastructure Layer
├── OpenAI API (Whisper, GPT)
├── SQLite Database (aiosqlite)
├── File System (音声一時保存)
└── External APIs (GitHub, Obsidian)
```

## コアコンポーネント

### 1. Bot Core (`src/nescordbot/`)

#### `bot.py` - NescordBot Class
```python
class NescordBot(commands.Bot):
    """メインBotクラス - commands.Bot継承"""

    # 初期化時にCog自動ロード
    # イベントリスナー（音声メッセージ検出）
    # グローバルエラーハンドリング
```

#### `main.py` - BotRunner
```python
class BotRunner:
    """Botライフサイクル管理"""

    # 設定読み込み
    # サービス初期化
    # Bot起動・停止
    # シグナルハンドリング
```

#### `__main__.py` - Entry Point
```python
# モジュール実行エントリー
# python -m nescordbot 対応
# main()関数呼び出し
```

### 2. Configuration (`config.py`)
```python
class Config(BaseSettings):
    """Pydantic設定管理"""

    discord_token: str              # Bot認証
    openai_api_key: str            # OpenAI API
    log_level: str = "INFO"        # ログレベル
    max_audio_size_mb: int = 25    # 音声ファイル上限
    speech_language: str = "ja-JP" # 音声認識言語

    # .env自動読み込み
    # 環境変数バリデーション
```

### 3. Logging (`logger.py`)
```python
def setup_logging(config: Config):
    """構造化ログ設定"""

    # コンソール + ファイル出力
    # カラーログ（colorlog）
    # レベル別フィルタリング
    # 非同期ログ対応
```

## Cogs System (Modular Commands)

### 4. General Commands (`cogs/general.py`)
```python
class GeneralCog(commands.Cog):
    """基本コマンド群"""

    @commands.hybrid_command()
    async def help(self, ctx):      # ヘルプ表示

    @commands.hybrid_command()
    async def status(self, ctx):    # Botステータス

    @commands.hybrid_command()
    async def ping(self, ctx):      # 応答速度測定
```

### 5. Voice Processing (`cogs/voice.py`)
```python
class VoiceCog(commands.Cog):
    """音声処理コマンド群"""

    async def transcribe_voice(self, attachment):
        # 1. 音声ファイルダウンロード
        # 2. OpenAI Whisper API呼び出し
        # 3. GPT による整形・要約
        # 4. 一時ファイル削除

    @commands.hybrid_command()
    async def transcribe(self, ctx):    # 手動文字起こし
```

### 6. Admin Commands (`cogs/admin.py`)
```python
class AdminCog(commands.Cog):
    """管理者コマンド群"""

    @commands.hybrid_command()
    async def logs(self, ctx):      # ログ表示

    @commands.hybrid_command()
    async def config(self, ctx):    # 設定表示

    @commands.hybrid_command()
    async def dbstats(self, ctx):   # DB統計
```

### 7. GitHub Integration (`cogs/github.py`)
```python
class GitHubCog(commands.Cog):
    """GitHub統合機能"""

    @commands.hybrid_command()
    async def issue(self, ctx):     # Issue管理

    @commands.hybrid_command()
    async def pr(self, ctx):        # PR管理

    @commands.hybrid_command()
    async def commit(self, ctx):    # コミット情報
```

### 8. Obsidian Integration (`cogs/obsidian.py`)
```python
class ObsidianCog(commands.Cog):
    """Obsidian vault連携"""

    @commands.hybrid_command()
    async def save_note(self, ctx): # ノート保存

    @commands.hybrid_command()
    async def search(self, ctx):    # ノート検索
```

## Services Layer (External Integration)

### 9. Database Service (`services/database.py`)
```python
class DatabaseService:
    """非同期SQLiteデータベース操作"""

    async def init_db(self):        # DB初期化
    async def save_transcription(self): # 文字起こし保存
    async def get_user_history(self):   # ユーザー履歴
    async def cleanup_old_data(self):   # 古いデータ削除

    # aiosqlite使用
    # コネクションプール管理
    # トランザクション制御
```

### 10. GitHub Service (`services/github.py`)
```python
class GitHubService:
    """GitHub API統合"""

    async def create_issue(self):   # Issue作成
    async def get_repositories(self): # リポジトリ一覧
    async def create_pr(self):      # PR作成

    # GitHub API v4 (GraphQL)
    # 認証トークン管理
    # レート制限処理
```

### 11. Obsidian Service (`services/obsidian.py`)
```python
class ObsidianService:
    """Obsidian vault操作"""

    async def save_to_vault(self):  # Vaultへ保存
    async def search_notes(self):   # ノート検索
    async def create_link(self):    # 内部リンク生成

    # ファイルシステム操作
    # Markdown形式処理
    # Vault構造管理
```

### 12. Service Container (`services/__init__.py`)
```python
class ServiceContainer:
    """依存注入コンテナ"""

    def __init__(self, config: Config):
        self.database = DatabaseService(config)
        self.github = GitHubService(config)
        self.obsidian = ObsidianService(config)

    # サービス依存関係管理
    # ライフサイクル制御
    # 設定共有
```

## 音声処理フロー詳細

### Event Flow
```
1. Discord Message Event (bot.py)
   ↓
2. Audio Attachment Detection
   ↓
3. File Download (data/ temporary)
   ↓
4. VoiceCog.transcribe_voice()
   ├── OpenAI Whisper API
   ├── Audio Format Validation
   └── Error Handling
   ↓
5. GPT Text Processing
   ├── Content Formatting
   ├── Summarization
   └── Language Enhancement
   ↓
6. Discord Response
   ├── Transcription Text
   ├── Interactive Buttons
   │   ├── Obsidian Save
   │   └── X (Twitter) Post
   └── Metadata (processing time, etc.)
   ↓
7. Cleanup (temporary files)
```

### Error Handling Strategy
```python
try:
    # OpenAI API Call
    transcription = await openai_client.transcribe(audio_file)
except openai.RateLimitError:
    # レート制限 - 待機後リトライ
except openai.APIError as e:
    # API エラー - ユーザーに通知
except Exception as e:
    # 予期しないエラー - ログ記録 + 汎用エラー
finally:
    # 一時ファイル削除
```

## データベーススキーマ

### Tables Structure
```sql
-- 文字起こし履歴
CREATE TABLE transcriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    guild_id TEXT,
    original_filename TEXT,
    transcription_text TEXT NOT NULL,
    processing_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ユーザー設定
CREATE TABLE user_settings (
    user_id TEXT PRIMARY KEY,
    preferred_language TEXT DEFAULT 'ja-JP',
    auto_save_obsidian BOOLEAN DEFAULT FALSE,
    auto_post_twitter BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- GitHubリポジトリ連携
CREATE TABLE github_repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    access_token TEXT,
    webhook_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 外部API統合

### OpenAI Integration
```python
# Whisper API (音声→テキスト)
response = await openai.Audio.atranscribe(
    model="whisper-1",
    file=audio_file,
    language="ja"
)

# GPT API (テキスト整形)
response = await openai.ChatCompletion.acreate(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": transcription}]
)
```

### Discord.py Integration
```python
# Hybrid Commands (Slash + Prefix)
@commands.hybrid_command(name="transcribe")
@app_commands.describe(language="音声認識言語")
async def transcribe_command(self, ctx: commands.Context, language: str = "ja-JP"):
    pass

# Event Listeners
@commands.Cog.listener()
async def on_message(self, message: discord.Message):
    # 音声添付ファイル検出
    # 自動処理開始
```

## Testing Architecture

### Test Structure
```
tests/
├── conftest.py                 # pytest設定・fixture
├── test_bot.py                 # Bot基本機能
├── test_bot_integration.py     # 統合テスト
├── test_cogs_general.py        # GeneralCogテスト
├── test_admin_cog.py          # AdminCogテスト
├── test_config.py             # 設定テスト
├── test_logger.py             # ログテスト
├── test_database_service.py   # DBサービステスト
└── test_services_github.py    # GitHubサービステスト
```

### Mock Strategy
```python
# Discord.py モック
@pytest.fixture
def mock_bot():
    return AsyncMock(spec=commands.Bot)

# OpenAI API モック
@patch('openai.Audio.atranscribe')
async def test_transcribe_success(mock_transcribe):
    mock_transcribe.return_value = {"text": "テスト結果"}
    # テスト実行
```

## Deployment Architecture

### Railway Deployment
```yaml
# railway.json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "poetry run python -m nescordbot",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100
  }
}
```

### Docker Architecture
```dockerfile
FROM python:3.11-slim
RUN pip install poetry
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev
COPY . .
CMD ["poetry", "run", "python", "-m", "nescordbot"]
```

### Environment Management
```bash
# Production
DISCORD_TOKEN=prod_token
OPENAI_API_KEY=prod_key
LOG_LEVEL=WARNING

# Development
DISCORD_TOKEN=dev_token
OPENAI_API_KEY=dev_key
LOG_LEVEL=DEBUG
```
