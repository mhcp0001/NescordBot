# Nescordbot (Python版)

Discord Bot with voice transcription and AI-powered features.

## 機能

- 🎤 音声メッセージの自動文字起こし（OpenAI Whisper）
- 🤖 AIによる内容整形（GPT-3.5/GPT-4）
- 📝 Obsidianへの自動保存（開発中）
- 🐦 X (Twitter) 投稿文の自動生成（開発中）
- 📊 メモの管理と検索

## 技術スタック

- **言語**: Python 3.11+
- **フレームワーク**: discord.py 2.3+
- **音声認識**: OpenAI Whisper API
- **AI処理**: OpenAI GPT API
- **非同期処理**: asyncio

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
# Poetry環境内で実行
poetry run python src/bot.py

# または Poetry シェル内で
poetry shell
python src/bot.py
```

## プロジェクト構造

```
Nescordbot/
├── src/
│   ├── bot.py          # メインのBotファイル
│   ├── cogs/           # コマンドモジュール
│   │   ├── general.py  # 一般コマンド
│   │   └── voice.py    # 音声処理コマンド
│   └── utils/          # ユーティリティ
├── data/               # ローカルデータ
├── pyproject.toml      # Poetry設定・依存関係
├── poetry.lock         # 依存関係のロックファイル（自動生成）
├── requirements.txt    # 互換性のため残す（自動生成可）
├── runtime.txt         # Pythonバージョン
├── Procfile           # PaaS用設定
└── .env               # 環境変数
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
# 必須
DISCORD_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key

# オプション
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
