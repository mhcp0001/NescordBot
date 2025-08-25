# Deployment Documentation

NescordBotのデプロイメント・セットアップに関するガイドです。

## 🚀 デプロイメントガイド

### [README.md](./README.md) (このファイル)
デプロイメント概要とガイド一覧

### [railway-guide.md](./railway-guide.md)
Railway PaaS特化のデプロイ手順
- Railway環境設定
- 環境変数設定
- 自動デプロイ設定

### [production-setup.md](./production-setup.md)
本番環境セットアップガイド
- セキュリティ設定
- 監視設定
- パフォーマンス最適化

### [complete-guide.md](./complete-guide.md)
包括的なデプロイメントガイド
- 開発環境から本番環境まで
- トラブルシューティング
- ベストプラクティス

## ⚡ クイックスタート

### 基本的なデプロイフロー
1. **環境準備**: Poetry, Python 3.11+
2. **依存関係**: `poetry install`
3. **環境変数**: `DISCORD_TOKEN`, `GEMINI_API_KEY`, `GITHUB_TOKEN`
4. **Railway設定**: 自動デプロイ有効化
5. **起動確認**: ヘルスチェック・ログ確認

### 必要な環境変数
```bash
DISCORD_TOKEN="your_discord_bot_token"
GEMINI_API_KEY="your_gemini_api_key"  # Phase 4でOpenAI APIから移行
GITHUB_TOKEN="your_github_token"
LOG_LEVEL="INFO"
```

## 🔧 技術要件

- **Python**: 3.11+
- **Memory**: 最低512MB推奨
- **Storage**: 1GB以上（ChromaDB用）
- **Network**: HTTPS対応

---

詳細な手順については、各ガイドを参照してください。
