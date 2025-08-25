# Architecture Documentation

NescordBotのシステムアーキテクチャと技術設計に関する文書です。

## 📋 文書一覧

### [overview.md](./overview.md)
システム全体のアーキテクチャ設計書
- コンポーネント構成
- データフロー
- 技術スタック

### [design/](./design/)
詳細設計文書
- [obsidian_github_integration.md](./design/obsidian_github_integration.md) - GitHub/Obsidian統合設計
- [text_message_fleeting_note.md](./design/text_message_fleeting_note.md) - テキストメッセージ処理設計

### [technical-specs/](./technical-specs/)
技術仕様書
- [task3-8-design.md](./technical-specs/task3-8-design.md) - Task 3.8設計書（Phase 3完了時）

## 🏗️ システム構成

```
Discord → SQLite(キュー+メタデータ) → GitHub(Obsidian-vault)
                ↓
          ChromaDB(ベクトル検索) ← Railway(ローカル検索システム)
```

## 🔧 技術スタック

- **Backend**: Python 3.11+ / discord.py 2.3+
- **Database**: SQLite + ChromaDB
- **AI API**: Google Gemini API
- **Hosting**: Railway PaaS
- **VCS**: GitHub

---

詳細な技術情報については、各文書を参照してください。
