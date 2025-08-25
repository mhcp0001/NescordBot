# Railway Deployment Guide

このガイドは、NescordBotをRailway.appにデプロイする手順を説明します。

## 前提条件

1. [Railway.app](https://railway.app)のアカウント
2. GitHubリポジトリの準備
3. 必要なAPIキーの取得
   - Discord Bot Token
   - OpenAI API Key

## デプロイ手順

### 1. Railway プロジェクトの作成

1. Railway.appにログイン
2. "New Project" → "Deploy from GitHub repo" を選択
3. NescordBotリポジトリを選択

### 2. 環境変数の設定

Railwayの環境変数設定で以下を追加：

```bash
# 必須設定
DISCORD_TOKEN=your_discord_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here

# オプション設定
LOG_LEVEL=INFO
MAX_AUDIO_SIZE_MB=25
SPEECH_LANGUAGE=ja
```

### 3. Discord Bot設定

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. 新しいApplicationを作成
3. Bot セクションでTokenを取得
4. OAuth2 セクションでBot権限を設定：
   - Send Messages
   - Use Slash Commands
   - Add Reactions
   - Read Message History
   - Use External Emojis

### 4. OpenAI API設定

1. [OpenAI Platform](https://platform.openai.com/api-keys)にアクセス
2. 新しいAPI Keyを作成
3. 使用量制限を設定（推奨）

## デプロイファイル説明

### `requirements.txt`
- 本番環境用Python依存関係
- 開発用パッケージは除外
- バージョン範囲指定で安定性確保

### `Procfile`
- Railway用プロセス定義
- `worker` タイプでBotを実行
- `run.py` をエントリーポイントとして使用

### `runtime.txt`
- Python バージョン指定 (3.11.11)
- Railway でのPython環境制御

### `nixpacks.toml`
- Nixpacks ビルド設定
- FFmpeg の自動インストール
- Python 3.11 環境セットアップ

### `railway.json`
- Railway デプロイ設定
- リスタートポリシー
- レプリカ数設定

## デプロイ後の確認

1. Railway のログでBot起動を確認
2. Discord サーバーでBotがオンラインになることを確認
3. `/help` コマンドで動作テスト
4. 音声メッセージの処理テスト

## トラブルシューティング

### よくある問題

1. **Bot がオンラインにならない**
   - Discord Token が正しいか確認
   - Bot の権限設定を確認

2. **OpenAI API エラー**
   - API Key が有効か確認
   - 使用量制限に達していないか確認

3. **FFmpeg エラー**
   - nixpacks.toml でFFmpegがインストールされているか確認

### ログの確認

Railway のログビューアーで以下を確認：
- 起動時のエラーメッセージ
- 環境変数の読み込み状況
- Discord への接続状況

## パフォーマンス最適化

### リソース使用量

- **CPU**: 軽負荷（通常 < 10%）
- **メモリ**: 50-100MB（Discord.py + NumPy）
- **ネットワーク**: OpenAI API使用時に増加

### スケーリング

- 小規模サーバー: 1レプリカで十分
- 大規模サーバー: 需要に応じてスケールアップ

## セキュリティ

1. **環境変数の管理**
   - APIキーをコードに含めない
   - Railway の環境変数機能を使用

2. **アクセス制限**
   - Bot の権限を最小限に設定
   - 不要な機能は無効化

3. **監視**
   - ログの定期的な確認
   - 異常な使用量の監視

## バックアップとメンテナンス

1. **設定のバックアップ**
   - 環境変数の記録
   - Bot設定のエクスポート

2. **定期メンテナンス**
   - 依存関係の更新
   - ログファイルのクリーンアップ
   - パフォーマンスの監視

## サポート

問題が発生した場合：

1. Railway のログを確認
2. GitHub Issues で報告
3. 設定の見直し

---

**注意**: このガイドは基本的なデプロイ手順です。本番環境では追加のセキュリティ設定や監視システムの導入を検討してください。
