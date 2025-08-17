# NescordBot ドキュメント

## 📚 ドキュメント構成

このディレクトリには、NescordBotプロジェクトに関する全てのドキュメントが格納されています。

### 📁 ディレクトリ構造

```
docs/
├── design/           # 設計書
├── requirements/     # 要件定義書
├── deployment/       # デプロイメント関連
├── operations/       # 運用・管理関連
├── archives/         # 完了済み・アーカイブ
└── README.md         # このファイル
```

---

## 📋 各ディレクトリの詳細

### 🎨 design/ - 設計書
システムアーキテクチャと詳細設計に関する文書

| ファイル名 | 内容 |
|-----------|------|
| `system_architecture.md` | システム全体のアーキテクチャ設計 |
| `obsidian_github_integration.md` | Obsidian GitHub統合の詳細設計 |

### 📝 requirements/ - 要件定義書
プロジェクトの要求事項と機能仕様

| ファイル名 | 内容 |
|-----------|------|
| `system_requirements.md` | システム全体の要件定義 |
| `obsidian_github_integration.md` | Obsidian GitHub統合の要件定義 |
| `original_development_foundation.md` | 原初開発基盤の要件定義 |

### 🚀 deployment/ - デプロイメント関連
本番環境への展開と運用設定

| ファイル名 | 内容 |
|-----------|------|
| `railway-deployment.md` | Railway PaaSへのデプロイ手順 |
| `complete-deployment-guide.md` | 包括的なデプロイメントガイド |

### ⚙️ operations/ - 運用・管理関連
プロジェクト管理と日常運用に関する文書

| ファイル名 | 内容 |
|-----------|------|
| `project-management.md` | プロジェクト管理手法と進行状況 |
| `tasks.md` | タスク管理とTODOリスト |
| `session_handover.md` | セッション引き継ぎ情報 |

### 📦 archives/ - アーカイブ
完了したフェーズや過去の文書

| ファイル名 | 内容 |
|-----------|------|
| `PHASE3_SUMMARY.md` | Phase 3完了サマリー |

---

## 🔍 ドキュメント検索ガイド

### 目的別ドキュメント検索

**新規開発者向け**:
1. `requirements/system_requirements.md` - プロジェクト概要
2. `design/system_architecture.md` - システム構造理解
3. `deployment/railway-deployment.md` - 開発環境構築

**機能開発向け**:
1. `requirements/` - 機能要件確認
2. `design/` - 実装設計参照
3. `operations/tasks.md` - 開発タスク確認

**運用・デプロイ向け**:
1. `deployment/` - デプロイメント手順
2. `operations/` - 運用手順と管理情報

### キーワード別ガイド

| 探している内容 | 参照すべきファイル |
|----------------|-------------------|
| システム全体の理解 | `design/system_architecture.md` |
| Obsidian統合機能 | `requirements/obsidian_github_integration.md`<br/>`design/obsidian_github_integration.md` |
| デプロイ手順 | `deployment/complete-deployment-guide.md` |
| Railway設定 | `deployment/railway-deployment.md` |
| プロジェクト進捗 | `operations/project-management.md` |
| 開発タスク | `operations/tasks.md` |

---

## 📝 ドキュメント更新ルール

### 新規ドキュメント作成時
1. 適切なディレクトリに配置
2. 命名規則に従う（小文字・アンダースコア区切り）
3. このREADME.mdの該当テーブルを更新

### 既存ドキュメント更新時
1. 変更履歴を文書内に記録
2. 大幅な変更時は旧版をarchives/に移動

### ドキュメント命名規則
- **英語ファイル名**: `snake_case.md`
- **内容説明的**: ファイル名から内容が推測可能
- **カテゴリ接頭辞**: 必要に応じて追加（例: `api_`, `user_`）

---

## 🔄 継続的改善

このドキュメント構造は、プロジェクトの成長に応じて継続的に改善されます。

- **定期レビュー**: 月次でドキュメント構造を見直し
- **アクセス分析**: よく参照される文書の特定
- **フィードバック収集**: 開発チームからの改善提案

---

*📅 最終更新: 2025-01-17*
*🔄 次回レビュー予定: 2025-02-17*
