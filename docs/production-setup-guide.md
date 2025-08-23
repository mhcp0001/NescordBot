# 本番環境セットアップガイド

## 概要

このドキュメントは、NescordBotの本番環境デプロイメント時に必要な設定項目と、Issue #89のようなFleeting Note機能の問題を防ぐための設定ガイドです。

## 必須環境変数

### 基本設定（必須）

```bash
# Discord Bot設定
DISCORD_TOKEN=your_discord_bot_token_here

# OpenAI API設定（音声認識・テキスト処理用）
OPENAI_API_KEY=your_openai_api_key_here
```

### Fleeting Note機能の設定（必須）

```bash
# Obsidian GitHub統合を有効にする
GITHUB_OBSIDIAN_ENABLED=true

# GitHub認証・リポジトリ設定
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REPO_OWNER=your_username
GITHUB_REPO_NAME=your_repository_name
```

### GitHub Tokenの権限要件

GitHub Tokenには以下の権限が必要です：

- `repo` - リポジトリへの読み取り・書き込みアクセス
- `contents` - ファイルの作成・更新（`repo`に含まれる）

**Token生成手順：**
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token" → "Generate new token (classic)"
3. Scopes で `repo` をチェック
4. Tokenを生成し、安全に保管

### オプション設定

```bash
# Obsidian GitHub統合の詳細設定
GITHUB_OBSIDIAN_BASE_PATH=obsidian_sync       # 保存先パス
GITHUB_OBSIDIAN_BRANCH=main                   # 使用ブランチ
GITHUB_OBSIDIAN_BATCH_SIZE=10                 # バッチサイズ
GITHUB_OBSIDIAN_BATCH_INTERVAL=300            # バッチ間隔（秒）

# Bot基本設定
LOG_LEVEL=INFO                                 # ログレベル
MAX_AUDIO_SIZE_MB=25                          # 最大音声ファイルサイズ
SPEECH_LANGUAGE=ja                            # 音声認識言語
DATABASE_URL=sqlite:///data/nescordbot.db     # データベースURL
```

## 本番環境での設定確認方法

### 1. デバッグコマンドを使用

```
/debug config
```

このコマンドで以下を確認できます：
- Obsidian GitHub統合の有効/無効状態
- 必須環境変数の設定状況
- サービスの初期化状態
- 推奨アクション

### 2. ログの確認

```
/logs
```

起動時のログで以下のメッセージを確認：

**正常な場合：**
```
ObsidianGitHub services initialized (async initialization pending)
ObsidianGitHub services fully initialized
```

**設定不備の場合：**
```
ObsidianGitHub integration disabled (github_obsidian_enabled=False)
To enable: Set GITHUB_OBSIDIAN_ENABLED=true in environment variables
```

または

```
ObsidianGitHub integration disabled (missing config: ['github_token', 'github_repo_owner'])
Required environment variables:
  - GITHUB_TOKEN
  - GITHUB_REPO_OWNER
```

## トラブルシューティング

### Issue #89: "Obsidian保存サービスが利用できません"

**症状：**
- Fleeting Note作成後、Obsidian保存ボタンが機能しない
- "❌ Obsidian保存サービスが利用できません" エラー

**原因：**
1. `GITHUB_OBSIDIAN_ENABLED=false` または未設定
2. 必須環境変数の不足（`GITHUB_TOKEN`, `GITHUB_REPO_OWNER`, `GITHUB_REPO_NAME`）
3. GitHub Tokenの権限不足

**解決方法：**
1. `/debug config` で設定状況確認
2. 不足している環境変数を設定
3. アプリケーションを再起動

### APIレート制限エラー

**症状：**
- "APIレート制限により処理できません" メッセージ

**原因：**
- OpenAI API のクォータ制限到達
- 無料プランの月間制限

**解決方法：**
1. OpenAI ダッシュボードでクォータ確認
2. 有料プランへのアップグレード検討
3. 使用量の最適化

## 推奨デプロイメント設定

### Railway

```bash
# Railway環境での設定例
railway variables set DISCORD_TOKEN="your_token"
railway variables set OPENAI_API_KEY="your_key"
railway variables set GITHUB_OBSIDIAN_ENABLED="true"
railway variables set GITHUB_TOKEN="your_github_token"
railway variables set GITHUB_REPO_OWNER="your_username"
railway variables set GITHUB_REPO_NAME="your_repo"
```

### Docker

```dockerfile
# Dockerfile example
ENV GITHUB_OBSIDIAN_ENABLED=true
ENV GITHUB_TOKEN=${GITHUB_TOKEN}
ENV GITHUB_REPO_OWNER=${GITHUB_REPO_OWNER}
ENV GITHUB_REPO_NAME=${GITHUB_REPO_NAME}
```

### Heroku

```bash
# Heroku Config Vars
heroku config:set GITHUB_OBSIDIAN_ENABLED=true
heroku config:set GITHUB_TOKEN=your_github_token
heroku config:set GITHUB_REPO_OWNER=your_username
heroku config:set GITHUB_REPO_NAME=your_repo
```

## 設定チェックリスト

### デプロイ前チェックリスト

- [ ] `DISCORD_TOKEN` 設定済み
- [ ] `OPENAI_API_KEY` 設定済み（有効なクォータ）
- [ ] `GITHUB_OBSIDIAN_ENABLED=true` 設定済み
- [ ] `GITHUB_TOKEN` 設定済み（repo権限付き）
- [ ] `GITHUB_REPO_OWNER` 設定済み
- [ ] `GITHUB_REPO_NAME` 設定済み
- [ ] GitHub リポジトリが存在し、アクセス可能

### デプロイ後チェックリスト

- [ ] Bot が正常に起動
- [ ] `/debug config` で全項目が ✅
- [ ] `/logs` で初期化ログを確認
- [ ] テキストメッセージでFleeting Note作成テスト
- [ ] Obsidian保存機能のテスト

## セキュリティ注意事項

1. **GitHub Token管理**
   - Token は environment variables で管理
   - ログに Token が出力されないよう注意
   - 定期的な Token のローテーション

2. **リポジトリアクセス制限**
   - 専用のリポジトリを使用
   - 必要最小限の権限を付与
   - プライベートリポジトリの使用を推奨

3. **OpenAI API Key管理**
   - API key の適切な管理
   - 使用量の監視
   - レート制限の設定

## 監視とメンテナンス

### 定期監視項目

- OpenAI API クォータ使用量
- GitHub API レート制限状況
- Fleeting Note 保存成功率
- エラーログの監視

### 月次メンテナンス

- GitHub Token の期限確認
- OpenAI クォータの確認
- ログファイルのローテーション

---

**最終更新:** 2025-08-23
**対応Issue:** #89 - [BUG] Fleeting Note processing fails in production
