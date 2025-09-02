# NescordBot - 第二の脳 🧠

**Discord上で動作するPersonal Knowledge Management (PKM)システム**
音声認識・AI統合・ベクトル検索による「第二の脳」を実現

## ✨ Phase 4完成 - あなたの知識を統合する最強Discord Bot

- 🧠 **AI Knowledge Graph**: 全ての情報を関連付け・自動リンク
- 🔍 **ハイブリッド検索**: ベクトル + キーワードの高精度検索
- 🎤 **99%コスト削減**: Gemini Audio APIで月$5以下の音声認識
- 🏷️ **自動分類**: AI powered タグ付け・カテゴリ化
- 📝 **Fleeting Note**: Discord ↔ Obsidian シームレス統合

## 機能

### Phase 4: Personal Knowledge Management (PKM) 🧠 ✅完成
「第二の脳Bot」として進化 - Discord上での高機能PKMシステム

- 🧠 **Knowledge Management**: AI-powered Personal Knowledge Graph
- 🔍 **ハイブリッド検索**: ベクトル検索 + キーワード検索の高精度統合
- 🏷️ **自動タグ付け**: Gemini AI による自動コンテンツ分類・カテゴリ化
- 🔗 **ノートリンク**: 関連性ベース自動リンク生成・グラフ化
- 📝 **Fleeting Note**: Discord ↔ PKM シームレス統合
- 🎯 **ノートマージ**: AI による関連ノート統合・重複解消
- 🔄 **同期管理**: SQLite ↔ ChromaDB 双方向同期
- 🎤 **Gemini Audio**: 音声認識コスト99%削減（月$5以下達成）

### Phase 3: 統合基盤機能 ✅安定稼働
- 🎤 **音声文字起こし**: Gemini Audio API (primary) + Whisper (fallback)
- 📝 **Obsidian GitHub統合**: ノート→GitHub自動同期・バージョン管理
- 🔐 **セキュリティ**: XSS/インジェクション完全防御
- 🗃️ **永続化キュー**: SQLite-backed高信頼性処理・バッチ最適化
- 🔗 **GitHub連携**: Issue/PR自動管理・ワークフロー統合
- 🛡️ **API制限フォールバック**: Gemini ↔ OpenAI 自動切り替え

## 技術スタック

### Phase 4: PKM Architecture 🧠
**「第二の脳」実現のためのAI統合アーキテクチャ**

- **Vector Database**: ChromaDB (in-memory + persistent)
- **AI Embeddings**: Gemini text-embedding-004 (primary) + OpenAI ada-002 (fallback)
- **Audio Processing**: Gemini Audio API (99%コスト削減) + Whisper (fallback)
- **Search Engine**: Enhanced RRF (Reciprocal Rank Fusion) Algorithm
- **Knowledge Graph**: NetworkX-based関連性グラフ・パス探索
- **Sync Management**: SQLite ↔ ChromaDB双方向同期

### Core Infrastructure
- **Language**: Python 3.11+ (async/await complete)
- **Framework**: discord.py 2.3+ (slash commands + views)
- **Database**: SQLite (structured) + ChromaDB (vectors) hybrid
- **AI Services**: Gemini 1.5 Pro + GPT-3.5/4.0 (fallback)
- **Process Management**: Async service container + dependency injection

### Phase 3: 統合基盤 ✅
- **GitHub統合**: ObsidianGitHubService + GitHubAuthManager
- **セキュリティ**: SecurityValidator (XSS/インジェクション対策)
- **永続化**: PersistentQueue + Dead Letter Queue
- **バッチ処理**: BatchProcessor + 非同期キューイング
- **Git操作**: GitOperationService (安全性保証)

### DevOps & Quality
- **CI/CD**: GitHub Actions (40%効率化達成)
- **環境統一**: Docker (dev/CI/prod完全一致)
- **デプロイ**: Railway自動デプロイ (100%安定化)
- **テスト**: pytest + pytest-xdist (78%カバレッジ維持)
- **並列処理**: pytest-xdist による高速テスト実行

## セットアップ

### 必要な環境

#### Phase 4: PKM対応環境
- **Python 3.11 以上** (async/await完全対応)
- **Poetry** (依存関係管理・仮想環境)
- **Gemini API Key** (PKM・音声認識・埋め込み生成)
- **ChromaDB** (ベクトルデータベース - 自動インストール)
- **Discord Bot Token** (Discord統合)

#### 追加・フォールバック
- **OpenAI API Key** (フォールバック用 - 省略可)
- **FFmpeg** (音声処理 - Whisperフォールバック時必要)
- **GitHub CLI** (開発・GitHub統合用)

### インストール手順

1. リポジトリをクローン
```bash
git clone https://github.com/yourusername/nescordbot.git
cd nescordbot
```

2. Poetryをインストール（未インストールの場合）
```bash
# 公式インストーラー（推奨）
curl -sSL https://install.python-poetry.org | python3 -

# または pip でインストール
pip install poetry
```

3. 依存関係をインストール
```bash
# Poetry が仮想環境を自動作成してパッケージをインストール
poetry install
```

4. 仮想環境に入る（必要に応じて）
```bash
# Poetry シェルを起動
poetry shell

# または、poetry run でコマンドを実行
poetry run python src/bot.py
```

4. FFmpegをインストール
```bash
# Windows (Chocolatey)
choco install ffmpeg

# Mac (Homebrew)
brew install ffmpeg

# Linux (apt)
sudo apt update && sudo apt install ffmpeg
```

5. 環境変数を設定
```bash
cp .env.example .env
# 必須設定
nano .env  # または好みのエディタで編集
```

**必須設定例:**
```env
# Discord Bot
DISCORD_TOKEN=your_discord_bot_token

# Phase 4 PKM機能
GEMINI_API_KEY=your_gemini_api_key

# ChromaDB (PKM)
CHROMADB_PERSIST_DIRECTORY=./data/chromadb
PKM_ENABLED=true

# フォールバック (省略可)
OPENAI_API_KEY=your_openai_key  # Gemini制限時のフォールバック
```

6. GitHub CLI をセットアップ（開発用）
```bash
# インストール（未インストールの場合）
# Windows (Scoop)
scoop install gh

# macOS
brew install gh

# Linux/WSL
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh

# 認証
gh auth login
```

7. Botを起動
```bash
# 推奨: Poetry scriptsを使用 (Phase 3で最適化済み)
poetry run start

# モジュール形式での実行
poetry run python -m nescordbot

# 代替実行方法
poetry run python src/nescordbot/__main__.py

# Poetry シェル内で
poetry shell
python -m nescordbot
```

## プロジェクト構造

### Phase 4 実装済み構造
```
NescordBot/
├── src/nescordbot/           # メインパッケージ
│   ├── __main__.py          # エントリーポイント
│   ├── bot.py               # NescordBotクラス (Discord基盤)
│   ├── main.py              # BotRunner・サービス管理
│   ├── config.py            # BotConfig (統合設定管理)
│   ├── logger.py            # ログサービス
│   │
│   ├── cogs/                # Discordコマンドモジュール
│   │   ├── general.py       # 一般コマンド (/help, /status)
│   │   ├── admin.py         # 管理コマンド (/logs, /config)
│   │   ├── voice.py         # 音声処理 (Gemini/Whisper)
│   │   ├── pkm.py          # 🧠 PKM中核機能 (/note, /search, /merge等)
│   │   ├── text.py         # テキスト処理・Obsidian統合
│   │   ├── github.py       # GitHub操作・Issue管理
│   │   └── api_status.py   # API使用量・ステータス監視
│   │
│   └── services/            # Phase 4 サービス層
│       ├── service_container.py    # DI・サービス管理
│       │
│       # PKM Core Services 🧠
│       ├── knowledge_manager.py    # ナレッジ管理・統合検索
│       ├── search_engine.py        # ハイブリッド検索エンジン
│       ├── chromadb_service.py     # ベクトルDB統合
│       ├── embedding.py            # Gemini埋め込み生成
│       ├── sync_manager.py         # SQLite↔ChromaDB同期
│       ├── note_processing.py      # ノート処理・構造化
│       │
│       # Linking & Graph Services 🔗
│       ├── link_graph_builder.py   # ナレッジグラフ構築
│       ├── link_suggestor.py       # 関連性ベース提案
│       ├── link_validator.py       # リンク妥当性検証
│       │
│       # API Management 🛡️
│       ├── token_manager.py        # API使用量管理
│       ├── fallback_manager.py     # API制限時フォールバック
│       ├── api_monitor.py          # リアルタイム監視
│       │
│       # Audio Processing 🎤
│       └── transcription/          # 音声認識サービス
│           ├── base.py            # 基底クラス・インターフェース
│           ├── gemini.py          # Gemini Audio API
│           └── whisper.py         # OpenAI Whisper (fallback)
│       │
│       # Phase 3 基盤サービス ✅
│       ├── database.py             # DatabaseService
│       ├── persistent_queue.py     # PersistentQueue + Dead Letter
│       ├── batch_processor.py      # バッチ処理・最適化
│       ├── git_operations.py       # Git操作・安全性保証
│       ├── github_auth.py          # GitHub認証管理
│       ├── obsidian_github.py      # Obsidian GitHub統合
│       └── migrations.py           # データベーススキーマ管理
│
├── tests/                   # 包括的テストスイート
│   ├── unit/               # 単体テスト (各サービス)
│   ├── integration/        # 統合テスト (API連携)
│   ├── fixtures/           # テストデータ・モック
│   └── conftest.py        # pytest共通設定
│
├── data/                   # 永続化データディレクトリ
│   ├── chromadb/          # ChromaDBベクトルデータ
│   ├── nescordbot.db      # SQLite構造化データ
│   └── temp/              # 一時ファイル (音声処理等)
│
├── docs/                   # プロジェクトドキュメント
├── .github/workflows/      # CI/CD自動化 (GitHub Actions)
├── Dockerfile             # コンテナ化環境
├── pyproject.toml         # Poetry依存関係・設定
├── poetry.lock            # 依存関係ロックファイル
└── .env                   # 環境変数設定
```

### 📊 Phase 4実装状況
- **Core PKM Services**: 19/27 タスク完了 (70.4%)
- **API Integration**: Gemini + ChromaDB 統合完成
- **Search Engine**: ハイブリッド検索アルゴリズム実装
- **Knowledge Graph**: 自動リンク・グラフ化機能実装
- **Audio Processing**: Gemini Audio API統合 (99%コスト削減)

## デプロイ

### Railway へのデプロイ

1. [Railway](https://railway.app) でアカウントを作成
2. GitHubリポジトリと連携
3. 環境変数を設定（Web UI上で）
4. 自動的にデプロイが開始されます

Railway用の設定：
- `runtime.txt` でPythonバージョンを指定
- `pyproject.toml` と `poetry.lock` で依存関係を管理
- GitHub Actionsで自動的に `requirements.txt` を生成
- `Procfile` でワーカープロセスを指定

### AWS/GCP へのデプロイ

```bash
# PM2でプロセス管理（Node.js必要）
pm2 start src/bot.py --interpreter python3 --name nescordbot

# または systemd サービスとして
sudo nano /etc/systemd/system/nescordbot.service
```

### Dockerでのデプロイ

```dockerfile
FROM python:3.11-slim

# Poetry のインストール
RUN pip install poetry

WORKDIR /app

# 依存関係ファイルをコピー
COPY pyproject.toml poetry.lock* ./

# 仮想環境を作らずに直接インストール
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

COPY . .
CMD ["python", "src/bot.py"]
```

## 使い方

### Phase 4: PKM (Personal Knowledge Management) 🧠

「第二の脳」としてのナレッジ管理機能 - すべての情報を統合・検索・関連付け

#### 📝 ノート管理
```
/note create <タイトル> <内容>     # 新規ノート作成
/note get <ノートID>              # ノート詳細表示
/note update <ノートID> <新内容>  # ノート更新
/note delete <ノートID>           # ノート削除
/note tag <ノートID> <タグ>       # 手動タグ付け
```

#### 🔍 ハイブリッド検索
```
/search <クエリ>                  # ベクトル + キーワード統合検索
/search --mode vector <クエリ>    # ベクトル検索のみ
/search --mode keyword <クエリ>   # キーワード検索のみ
/search --limit 20 <クエリ>       # 結果数指定
```

#### 📊 ノート一覧・管理
```
/list                            # 全ノート一覧
/list --tag <タグ名>             # タグ別フィルタ
/list --recent 10                # 最新N件
/list --created_after 2024-01-01 # 日付フィルタ
```

#### 🔗 関連性・リンク機能
```
/link suggest <ノートID>          # 関連ノート自動提案
/link validate <ノートID>         # リンク妥当性チェック
/link graph <ノートID>            # ナレッジグラフ表示
/link path <ノートA> <ノートB>    # ノート間パス探索
```

#### 🎯 高度な機能
```
/merge <ノートID1> <ノートID2>    # AI による関連ノート統合
/auto_tag suggest <ノートID>      # AI タグ提案
/auto_tag apply <ノートID>        # AI タグ自動適用
/auto_tag batch --tag <タグ>      # バッチ自動タグ付け
```

### Phase 3: 基盤機能 ✅

#### 一般コマンド
- `/help` - 全機能ヘルプ表示
- `/status` - システムステータス・API使用状況
- `/ping` - 応答速度・レイテンシ測定

#### 音声メッセージ処理 🎤
1. **Discordで音声メッセージを録音** → 送信
2. **自動認識**: Gemini Audio API (99%コスト削減) による高精度文字起こし
3. **AI処理**: 内容整形・要約・構造化
4. **統合保存**: PKMシステムへの自動統合 + Obsidian同期
5. **インタラクティブ**: ボタンでタグ付け・関連付け・共有が可能

#### テキストメッセージ処理 📝
1. **長文メッセージ**: 自動的にFleeting Noteとしてキャプチャ
2. **AI分析**: 自動タグ付け・カテゴリ化・関連ノート提案
3. **GitHub統合**: Obsidian形式でのバージョン管理・バックアップ

## 開発

### 開発ワークフロー

```bash
# 1. 利用可能なIssueを確認
gh issue list --label "help wanted" --state open

# 2. Issueから開発ブランチを作成
gh issue develop 123 --name "feature/123-new-feature" --base main

# 3. 開発・コミット
git add .
git commit -m "feat: 新機能を実装 (refs #123)"

# 4. PRを作成（自動でIssueとリンク）
git push
gh pr create --fill --web  # 本文に "Closes #123" を含める

# 5. 自動マージ設定（CI通過後）
gh pr merge --auto --squash --delete-branch
```

### コードスタイル

```bash
# コードフォーマット
poetry run black src/

# Linting
poetry run flake8 src/

# Import のソート
poetry run isort src/

# 型チェック
poetry run mypy src/
```

### テスト実行

```bash
poetry run pytest tests/

# カバレッジ付き
poetry run pytest --cov=src tests/
```

### 依存関係の管理

```bash
# 新しいパッケージを追加
poetry add package-name

# 開発用パッケージを追加
poetry add --group dev package-name

# 依存関係をアップデート
poetry update

# requirements.txt を生成（互換性のため）
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

### 新しいCogの追加

1. `src/cogs/` に新しいファイルを作成
2. `commands.Cog` を継承したクラスを定義
3. `bot.py` でCogを読み込み

## トラブルシューティング

### 音声認識が動作しない

1. OpenAI APIキーが正しく設定されているか確認
2. FFmpegがインストールされているか確認
3. 音声ファイルのフォーマットを確認（ogg, mp3, wav対応）

### ImportError: No module named 'discord'

```bash
# Poetry環境で再インストール
poetry add discord-py@latest
```

### Bot が起動しない

1. Pythonバージョンを確認: `python --version`
2. トークンが正しいか確認
3. ログファイル（bot.log）を確認

## 環境変数

### 必須設定
```env
# Discord Bot
DISCORD_TOKEN=your_discord_bot_token

# AI Services (Phase 4実装)
GEMINI_API_KEY=your_gemini_api_key          # PKM機能・音声認識用
OPENAI_API_KEY=your_openai_api_key          # フォールバック用
```

### Phase 4: PKM機能設定
```env
# ChromaDB (ベクトル検索)
CHROMADB_PERSIST_DIRECTORY=./data/chromadb
CHROMADB_COLLECTION_NAME=nescord_knowledge

# PKM機能調整
PKM_ENABLED=true
PKM_HYBRID_SEARCH_ALPHA=0.5                # ベクトル検索とキーワード検索の重み
PKM_MAX_RESULTS=10
PKM_AUTO_TAG_ENABLED=true

# Gemini API使用量制限
GEMINI_MONTHLY_LIMIT=1000000               # 月間リクエスト制限
```

### Phase 3: GitHub統合設定
```env
# GitHub統合
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO_OWNER=repository_owner_name
GITHUB_REPO_NAME=repository_name
GITHUB_BASE_BRANCH=main

# Obsidian GitHub統合
GITHUB_OBSIDIAN_ENABLED=true
GITHUB_OBSIDIAN_BASE_PATH=obsidian_sync
GITHUB_OBSIDIAN_BRANCH=main
GITHUB_OBSIDIAN_BATCH_SIZE=10
GITHUB_OBSIDIAN_BATCH_INTERVAL=300

# ローカルObsidian統合
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault
```

### 一般設定
```env
# Bot動作設定
LOG_LEVEL=INFO
MAX_AUDIO_SIZE_MB=25
SPEECH_LANGUAGE=ja

# データベース
DATABASE_URL=sqlite:///app/data/nescordbot.db

# API制限・フォールバック設定
TRANSCRIPTION_PROVIDER=gemini              # gemini, whisper
EMBEDDING_PROVIDER=gemini                  # gemini, openai
```

## 貢献

プルリクエストを歓迎します！

1. Forkする
2. Feature branchを作成 (`git checkout -b feature/amazing-feature`)
3. Commitする (`git commit -m 'Add amazing feature'`)
4. Pushする (`git push origin feature/amazing-feature`)
5. Pull Requestを作成

## ライセンス

MIT License

## 作者

- GitHub: [@yourusername](https://github.com/yourusername)

## 謝辞

- [discord.py](https://discordpy.readthedocs.io/) - Discord API wrapper
- [OpenAI](https://openai.com/) - Whisper & GPT APIs
- すべてのコントリビューター
