# NescordBot プロジェクト概要

## プロジェクトの目的
NescordBotは、音声文字起こしとAI機能を備えたDiscord Botです。主な機能：

- 🎤 音声メッセージの自動文字起こし（OpenAI Whisper）
- 🤖 AIによる内容整形（GPT-3.5/GPT-4）
- 📝 Obsidianへの自動保存（開発中）
- 🐦 X (Twitter) 投稿文の自動生成（開発中）
- 📊 メモの管理と検索

## 技術スタック

### 言語・フレームワーク
- **Python 3.11+**: メイン言語
- **discord.py 2.3+**: Discord API wrapper
- **asyncio**: 非同期処理
- **Poetry**: 依存関係管理・仮想環境

### AI・音声処理
- **OpenAI Whisper API**: 音声認識
- **OpenAI GPT API**: テキスト処理・要約
- **FFmpeg**: 音声ファイル処理
- **pydub**: Python音声処理ライブラリ

### データベース・ストレージ
- **aiosqlite**: 非同期SQLite操作
- **aiofiles**: 非同期ファイル操作

### 開発・品質管理
- **pytest + pytest-asyncio**: テスティングフレームワーク
- **pytest-xdist**: 並列テスト実行
- **black**: コードフォーマッター（line-length: 100）
- **isort**: import文ソート
- **ruff**: 高速linter
- **mypy**: 型チェック
- **pre-commit**: Git hook管理
- **GitHub CLI**: Issue・PR管理自動化

## アーキテクチャ構造

### コアディレクトリ
```
src/nescordbot/
├── bot.py              # NescordBot クラス（commands.Bot継承）
├── main.py             # BotRunner・サービス管理
├── __main__.py         # モジュールエントリーポイント
├── config.py           # Pydantic設定管理
├── logger.py           # ログサービス設定
├── cogs/               # モジュラーコマンドグループ
│   ├── general.py      # 一般コマンド（/help, /status, /ping）
│   ├── admin.py        # 管理コマンド（/logs, /config, /dbstats）
│   ├── voice.py        # 音声処理（Whisper文字起こし・GPT処理）
│   ├── github.py       # GitHub統合
│   └── obsidian.py     # Obsidian vault連携
└── services/           # データ永続化・外部統合
    ├── database.py     # DatabaseService（aiosqlite）
    ├── github.py       # GitHubService
    ├── obsidian.py     # ObsidianService
    └── __init__.py     # サービスコンテナ・DI
```

### 音声メッセージ処理フロー
1. ユーザーが音声メッセージ送信 → bot.py が音声添付検出
2. data/ ディレクトリに一時ファイルダウンロード
3. voice.py cog でOpenAI Whisper API経由文字起こし
4. GPT でフォーマット・要約処理
5. インタラクティブボタン付き結果返信（Obsidian保存・X投稿 - 実装中）
6. 一時ファイル削除

## 必要な環境変数
- `DISCORD_TOKEN`: Bot認証トークン（必須）
- `OPENAI_API_KEY`: Whisper・GPT API用（必須）
- `LOG_LEVEL`: ログレベル（オプション）
- `MAX_AUDIO_SIZE_MB`: 最大音声ファイルサイズ（オプション、デフォルト25MB）
- `SPEECH_LANGUAGE`: 音声認識言語（オプション）

## デプロイ対応
- **Railway**: 主要デプロイ先（Procfile, railway.json）
- **Docker**: Dockerfile対応
- **AWS/GCP**: systemd service対応
- **GitHub Actions**: CI/CD自動化
