# NescordBot 完全デプロイガイド

このガイドでは、NescordBotをRailwayにデプロイし、自分のDiscordサーバーに追加する完全な手順を説明します。

## 📋 事前準備

### 必要なアカウント
- [GitHub](https://github.com) アカウント
- [Railway.app](https://railway.app) アカウント
- [Discord](https://discord.com) アカウント
- [OpenAI](https://platform.openai.com) アカウント

### 推定時間
- 全体: 約30-45分
- Discord Bot作成: 10分
- OpenAI API設定: 5分
- Railway設定: 15分
- テスト: 5-10分

---

## 🤖 Step 1: Discord Bot の作成

### 1.1 Discord Developer Portal にアクセス

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. 右上の **"New Application"** をクリック
3. アプリケーション名を入力（例: "NescordBot"）
4. **"Create"** をクリック

### 1.2 Bot の設定

1. 左メニューから **"Bot"** を選択
2. **"Add Bot"** → **"Yes, do it!"** をクリック
3. **重要**: **"Token"** をコピーして安全な場所に保存
   ```
   例: MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234
   ```

### 1.3 Bot の権限設定

1. **"Privileged Gateway Intents"** セクションで以下を有効化:
   - ✅ **MESSAGE CONTENT INTENT** (メッセージ内容読み取り)
   - ✅ **SERVER MEMBERS INTENT** (サーバーメンバー情報)

### 1.4 OAuth2 URL の生成

1. 左メニューから **"OAuth2"** → **"URL Generator"** を選択
2. **"Scopes"** で以下を選択:
   - ✅ `bot`
   - ✅ `applications.commands`

3. **"Bot Permissions"** で以下を選択:
   ```
   General Permissions:
   ✅ Read Messages/View Channels

   Text Permissions:
   ✅ Send Messages
   ✅ Use Slash Commands
   ✅ Embed Links
   ✅ Attach Files
   ✅ Read Message History
   ✅ Add Reactions
   ✅ Use External Emojis

   Voice Permissions:
   (現在は不要、将来の機能用)
   ```

4. 生成された **"GENERATED URL"** をコピー
   ```
   例: https://discord.com/api/oauth2/authorize?client_id=123456789&permissions=274877984768&scope=bot%20applications.commands
   ```
https://discord.com/oauth2/authorize?client_id=1391291495025217616&permissions=0&integration_type=0&scope=bot+applications.commands

---

## 🔑 Step 2: OpenAI API Key の取得

### 2.1 OpenAI アカウント設定

1. [OpenAI Platform](https://platform.openai.com) にアクセス
2. アカウントにログイン
3. 右上のメニューから **"API keys"** を選択

### 2.2 API Key の作成

1. **"Create new secret key"** をクリック
2. 名前を入力（例: "NescordBot"）
3. **"Create secret key"** をクリック
4. **重要**: 表示されたAPI Keyをコピーして安全な場所に保存
   ```
   例: sk-abcdef1234567890abcdef1234567890abcdef1234567890ab
   ```
5. ⚠️ **この画面を閉じると二度と表示されません**

### 2.3 使用量制限の設定（推奨）

1. **"Usage"** → **"Limits"** に移動
2. 月額使用量制限を設定（例: $10-20）
3. **"Save"** をクリック

---

## 🚂 Step 3: Railway でのデプロイ

### 3.1 Railway アカウント設定

1. [Railway.app](https://railway.app) にアクセス
2. **"Login"** → **"Login with GitHub"** でGitHubアカウント連携
3. GitHubアカウントでログイン

### 3.2 プロジェクト作成

1. ダッシュボードで **"New Project"** をクリック
2. **"Deploy from GitHub repo"** を選択
3. **"Configure GitHub App"** で以下を設定:
   - Repository access: **"Selected repositories"**
   - NescordBotリポジトリを選択
   - **"Install & Authorize"** をクリック

### 3.3 リポジトリ選択

1. **"Deploy from GitHub repo"** 画面でNescordBotリポジトリを選択
2. 自動的にデプロイが開始されます

### 3.4 環境変数の設定

1. プロジェクトダッシュボードで **"Variables"** タブをクリック
2. 以下の環境変数を追加:

   ```bash
   # 必須設定
   DISCORD_TOKEN = MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234
   OPENAI_API_KEY = sk-abcdef1234567890abcdef1234567890abcdef1234567890ab

   # オプション設定（推奨）
   LOG_LEVEL = INFO
   MAX_AUDIO_SIZE_MB = 25
   SPEECH_LANGUAGE = ja
   ```

3. 各変数を追加後 **"Add"** をクリック

### 3.5 デプロイ確認

1. **"Deployments"** タブでデプロイ状況を確認
2. ログに以下が表示されれば成功:
   ```
   🚀 Starting NescordBot...
   ✅ Bot logged in as NescordBot#1234 (ID: 123456789)
   ✅ Bot is ready and online!
   ```

---

## 📱 Step 4: Discord サーバーに Bot を追加

### 4.1 Bot をサーバーに招待

1. Step 1.4 で生成したOAuth2 URLにアクセス
2. **"Add to Server"** ドロップダウンで自分のサーバーを選択
3. 権限を確認して **"Authorize"** をクリック
4. CAPTCHAを完了

### 4.2 Bot の動作確認

1. Discordサーバーで Bot がオンラインになっているか確認
2. 以下のスラッシュコマンドをテスト:

   **基本コマンド:**
   ```
   /help    - Bot の使い方を表示
   /ping    - 応答速度をテスト
   /status  - Bot の動作状況を確認
   ```

### 4.3 音声メッセージテスト

1. Discordの音声メッセージ機能を使用
2. 短い音声メッセージを送信
3. Bot が反応することを確認:
   - ⏳ 処理中リアクション
   - ✅ 完了リアクション
   - 📝 確認メッセージ

---

## 🔧 トラブルシューティング

### Bot がオンラインにならない場合

**原因 1: Discord Token エラー**
```bash
# Railway ログで確認
❌ Failed to start bot: Improper token has been passed
```
**解決策:**
- Discord Developer Portal でTokenを再生成
- Railway の環境変数を更新

**原因 2: 権限不足**
```bash
# ログに権限エラーが表示
❌ Missing Permissions
```
**解決策:**
- OAuth2 URL を再生成して権限を追加
- Bot を一度サーバーから削除し、再招待

### OpenAI API エラー

**原因: API Key 無効またはクレジット不足**
```bash
# ログでAPI エラーを確認
❌ OpenAI API error: Invalid API key
```
**解決策:**
- OpenAI Platform でAPI Key を確認
- クレジット残高を確認
- 使用量制限を確認

### Railway デプロイエラー

**原因 1: Docker ビルド内部エラー**
```bash
panic: send on closed channel
Error: Docker build failed
```
**解決策:**
1. Railway ダッシュボードで "Redeploy" をクリック
2. それでも失敗する場合は以下を確認：
   - nixpacks.toml でFFmpeg設定を削除
   - requirements.txt でFFmpeg関連依存を一時的にコメントアウト
   - .dockerignore を追加してビルド最適化

**原因 2: 依存関係ビルドエラー**
```bash
# デプロイログでエラー確認
❌ Build failed
```
**解決策:**
- requirements.txt の依存関係を確認
- Python バージョンを確認 (3.11+)
- ログの詳細エラーメッセージを確認

---

## 📊 動作確認チェックリスト

### ✅ 必須確認項目

- [ ] Bot がDiscordサーバーでオンライン表示
- [ ] `/help` コマンドが正常に動作
- [ ] `/ping` コマンドで応答時間が表示
- [ ] `/status` コマンドでシステム情報が表示
- [ ] 音声メッセージに Bot が反応
- [ ] Railway のログでエラーが出ていない

### ✅ オプション確認項目

- [ ] Bot のプロフィール画像設定
- [ ] カスタムステータス表示
- [ ] サーバー固有の権限設定
- [ ] ログの定期的な監視設定

---

## 🛡️ セキュリティとメンテナンス

### セキュリティベストプラクティス

1. **トークン管理**
   - Discord Token と OpenAI API Key を誰にも教えない
   - 定期的なトークンローテーション（3-6ヶ月）

2. **権限管理**
   - Bot に必要最小限の権限のみ付与
   - 定期的な権限の見直し

3. **監視**
   - Railway ログの定期確認
   - 異常なAPI使用量の監視

### 定期メンテナンス

1. **月次タスク**
   - [ ] ログの確認とクリーンアップ
   - [ ] OpenAI API 使用量の確認
   - [ ] Bot のパフォーマンス確認

2. **四半期タスク**
   - [ ] 依存関係の更新確認
   - [ ] セキュリティアップデート適用
   - [ ] バックアップ設定の確認

---

## 🆘 サポートとリソース

### 公式ドキュメント
- [Discord Developer Documentation](https://discord.com/developers/docs)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Railway Documentation](https://docs.railway.app)

### コミュニティサポート
- [Discord.py サーバー](https://discord.gg/dpy)
- [Railway コミュニティ](https://discord.gg/railway)

### 緊急時の対応

**Bot が停止した場合:**
1. Railway ダッシュボードでログを確認
2. 環境変数が正しく設定されているか確認
3. Discord・OpenAI のサービス状況を確認
4. 必要に応じて Railway でサービスを再起動

---

## 🎉 完了！

おめでとうございます！NescordBot が正常にデプロイされ、あなたのDiscordサーバーで動作しています。

**次のステップ:**
- Bot の使い方をサーバーメンバーに共有
- 音声メッセージ機能のテスト
- 将来の機能追加の計画

何か問題が発生した場合は、このガイドのトラブルシューティングセクションを参照するか、GitHub Issues で報告してください。
