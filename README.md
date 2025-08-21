# Nescordbot (Python版)

Discord Bot with voice transcription and AI-powered features.

## 機能

- 🎤 音声メッセージの自動文字起こし（OpenAI Whisper）
- 🤖 AIによる内容整形（GPT-3.5/GPT-4）
- 📝 **Obsidian GitHub統合**: ノート→GitHub自動同期 ✅
- 🔐 **セキュリティ**: XSS/インジェクション完全防御 ✅
- 🗃️ **永続化キュー**: SQLite-backed高信頼性処理 ✅
- 🔗 **GitHub連携**: Issue/PR自動管理 ✅
- 📊 メモの管理と検索

## 技術スタック

### コア技術
- **言語**: Python 3.11+
- **フレームワーク**: discord.py 2.3+
- **音声認識**: OpenAI Whisper API
- **AI処理**: OpenAI GPT API
- **非同期処理**: asyncio + aiosqlite

### 統合機能 (Phase 3完了 ✅)
- **GitHub統合**: ObsidianGitHubService + GitHubAuthManager
- **セキュリティ**: SecurityValidator (XSS/インジェクション対策)
- **永続化**: PersistentQueue + Dead Letter Queue
- **バッチ処理**: BatchProcessor + 非同期キューイング
- **Git操作**: GitOperationService (安全性保証)

### CI/CD基盤
- **CI/CD**: GitHub Actions (40%効率化達成)
- **環境統一**: Docker (dev/CI/prod完全一致)
- **デプロイ**: Railway自動デプロイ (100%安定化)
- **テスト**: pytest + pytest-xdist (78%カバレッジ)

## セットアップ

### 必要な環境

- Python 3.11 以上
- Poetry（依存関係管理）
- FFmpeg（音声処理用）
- GitHub CLI（開発用）
- Discord Bot Token
- OpenAI API Key

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
# .envファイルを編集して、必要なトークンとAPIキーを設定
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

```
NescordBot/
├── src/nescordbot/           # メインパッケージ
│   ├── __main__.py          # エントリーポイント
│   ├── bot.py               # NescordBotクラス
│   ├── main.py              # BotRunner・サービス管理
│   ├── config.py            # BotConfig (GitHub統合)
│   ├── logger.py            # ログサービス
│   ├── cogs/                # コマンドモジュール
│   │   ├── general.py       # 一般コマンド
│   │   ├── admin.py         # 管理コマンド
│   │   └── voice.py         # 音声処理コマンド
│   └── services/            # サービス層 (Phase 3実装)
│       ├── __init__.py      # サービスコンテナ
│       ├── database.py      # DatabaseService
│       ├── security.py      # SecurityValidator
│       ├── persistent_queue.py  # PersistentQueue
│       ├── git_operations.py    # GitOperationService
│       ├── github_auth.py       # GitHubAuthManager
│       ├── batch_processor.py   # BatchProcessor
│       └── obsidian_github.py   # ObsidianGitHubService
├── tests/                   # テストスイート (78%カバレッジ)
├── docs/                    # ドキュメント
├── data/                    # ローカルデータ
├── .github/workflows/       # CI/CD (GitHub Actions)
├── Dockerfile              # Docker環境統一
├── pyproject.toml          # Poetry設定・依存関係
├── poetry.lock             # 依存関係ロック
└── .env                    # 環境変数
```

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

### スラッシュコマンド

- `/help` - ヘルプを表示
- `/status` - Botのステータスを確認
- `/ping` - 応答速度を確認

### 音声メッセージ

1. Discordで音声メッセージを録音
2. 送信すると自動的に処理開始
3. 文字起こし結果が返信される
4. ボタンでObsidian保存やX投稿が可能

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

```env
# 必須 - Discord Bot
DISCORD_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key

# GitHub統合 (Phase 3実装済み)
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO_OWNER=repository_owner_name
GITHUB_REPO_NAME=repository_name
GITHUB_BASE_BRANCH=main

# Obsidian統合
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault

# オプション設定
LOG_LEVEL=INFO
MAX_AUDIO_SIZE_MB=25
SPEECH_LANGUAGE=ja-JP
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
