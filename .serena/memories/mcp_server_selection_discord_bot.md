# MCP Server選定ガイド - Discord Bot開発プロジェクト向け

## 概要
NescordBot（Discord音声転写bot）プロジェクトでのMCP Server選定検討結果と判断基準

## プロジェクト特性
- **技術スタック**: Python, discord.py, OpenAI API (Whisper/GPT), aiosqlite, Poetry
- **機能**: Discord音声メッセージの転写とAI処理
- **インフラ**: GitHub Actions CI/CD → Railway/AWS自動デプロイ

## 最終選定結果（必要十分な4つ）

### ✅ 採用MCPサーバー
1. **serena** - コードベース分析とプロジェクト管理
2. **gemini-yusukedev** - 技術的助言とリサーチ
3. **github** - Issue/PR管理、CI/CD統合
4. **context7** - ライブラリAPI仕様参照（discord.py, OpenAI等）

## 検討したが不要と判断したMCPサーバー

### discord-mcp
**誤解されやすいポイント**
- **本来の用途**: ClaudeがDiscordサーバーと直接やり取りするためのMCP
- **Bot開発との関係**: Discord BotそのものがDiscord APIと通信する主体
- **判断**: Bot開発には不要（Bot自体がDiscordとの通信層）

### playwright
**不要理由**
- Discord botはWebUIを持たない
- APIベースの通信のため、UIテスト対象が存在しない
- discord.pyのモックテストで十分

### notion
**不要理由**
- ドキュメント管理はGitHub（README, docs/, Wiki）で完結
- 個人プロジェクトのため、チーム共有の必要性が低い
- 将来Obsidian連携実装時に再検討

### markitdown
**不要理由**
- 音声転写結果の整形はGPTで処理済み
- Markdown変換の特別な需要なし

### sqlite-explorer系
**不要理由**
- デバッグ機会が現時点で少ない
- aiosqliteの基本機能で十分
- 必要になったら追加検討

### docker-mcp
**不要理由**
- GitHub Actions経由での自動デプロイが構築済み
- ローカルテストはdocker-composeで十分
- CI/CDパイプラインで環境管理が完結

### monitoring系（datadog等）
**不要理由**
- GitHub Actionsのステータスで基本的な監視は可能
- 小規模プロジェクトには過剰
- 本番環境の規模拡大時に再検討

## MCPサーバー選定の判断基準

### 採用すべき場合
1. **プロジェクト固有の課題を直接解決**
   - 例: serenaでのコード分析、githubでのIssue管理
2. **頻繁に使用する機能**
   - 例: geminiでの技術相談、context7でのAPI仕様確認
3. **他のツールで代替困難**
   - 例: serenaの高度なコード解析機能

### 不要と判断すべき場合
1. **既存の仕組みと重複**
   - 例: docker-mcp vs GitHub Actions
2. **プロジェクトの性質と不一致**
   - 例: playwrightとCLI/APIベースのbot
3. **現時点で需要がない**
   - 例: SQLiteデバッグツール
4. **役割を誤解している**
   - 例: discord-mcpをBot開発ツールと誤認

## ベストプラクティス

### シンプルさの維持
- 必要最小限のMCPサーバーに留める
- 起動時間とメンテナンス性を重視
- 認知負荷を最小化

### 段階的導入
- まず必須機能から導入
- 実際の需要が発生してから追加検討
- 定期的に使用状況をレビュー

### プロジェクト特性の考慮
- WebアプリとCLI/Botの違いを認識
- チーム規模に応じた選定
- 既存インフラとの統合性を評価

## 将来の再検討トリガー

以下の場合は追加MCPサーバーを検討：
1. **Obsidian連携実装時** → notion/markitdown再検討
2. **チーム開発移行時** → notion等の共有ツール検討
3. **本番環境の規模拡大時** → monitoring系導入
4. **WebUI追加時** → playwright導入
5. **データベース移行時** → 対応するDB用MCP導入

## まとめ

Discord Bot開発において、現在の4つのMCPサーバー構成（serena, gemini-yusukedev, github, context7）は必要十分。追加のMCPサーバーは、具体的な需要が発生するまで導入を見送ることで、シンプルで効率的な開発環境を維持できる。
