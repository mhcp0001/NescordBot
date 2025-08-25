# Phase 4 GitHub Project Item ID 参照表

開発時のステータス更新で使用するプロジェクトアイテムIDの参照表です。

## Status Update Constants

```bash
# Nescord Project Constants
PROJECT_ID="PVT_kwHOAVzM6c4BAoYL"
STATUS_FIELD_ID="PVTSSF_lAHOAVzM6c4BAoYLzgzYKtg"
TODO_ID="f75ad846"
IN_PROGRESS_ID="47fc9ee4"
DONE_ID="98236657"
```

## Phase 4 Task Project Item IDs

| Task | Issue# | Title | Project Item ID |
|------|--------|-------|----------------|
| 4.1.1 | #95 | ServiceContainer Phase 4拡張 | `PVTI_lAHOAVzM6c4BAoYLzgd90Rw` |
| 4.1.2 | #96 | BotConfig Gemini・ChromaDB設定追加 | `PVTI_lAHOAVzM6c4BAoYLzgd90TQ` |
| 4.1.3 | #97 | データベーススキーマ拡張 | `PVTI_lAHOAVzM6c4BAoYLzgd90VU` |
| 4.1.4 | #98 | TokenManager実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90YQ` |
| 4.1.5 | #99 | EmbeddingService (Gemini API統合) | `PVTI_lAHOAVzM6c4BAoYLzgd90aM` |
| 4.1.6 | #100 | ChromaDBService実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90bA` |
| 4.1.7 | #101 | Railway Persistent Volumes設定・検証 | `PVTI_lAHOAVzM6c4BAoYLzgd90bs` |
| 4.1.8 | #102 | SyncManager基本機能 | `PVTI_lAHOAVzM6c4BAoYLzgd90b0` |
| 4.2.1 | #103 | KnowledgeManager中核実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90b4` |
| 4.2.2 | #104 | SearchEngine基本実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90cE` |
| 4.2.3 | #105 | PKMCog基本コマンド実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90cM` |
| 4.2.4 | #106 | ハイブリッド検索実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90cQ` |
| 4.2.5 | #107 | ノートリンク機能実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90cY` |
| 4.2.6 | #108 | Gemini Audio API移行 (VoiceCog統合) | `PVTI_lAHOAVzM6c4BAoYLzgd90cc` |
| 4.3.1 | #109 | /merge コマンド実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90ck` |
| 4.3.2 | #110 | 自動タグ付け・カテゴリ化 | `PVTI_lAHOAVzM6c4BAoYLzgd90co` |
| 4.3.3 | #111 | Fleeting Note処理拡張 | `PVTI_lAHOAVzM6c4BAoYLzgd90c0` |
| 4.3.4 | #112 | バッチ処理最適化 | `PVTI_lAHOAVzM6c4BAoYLzgd90c8` |
| 4.3.5 | #113 | API制限時フォールバック機能 | `PVTI_lAHOAVzM6c4BAoYLzgd90dA` |
| 4.4.1 | #114 | Phase4Monitor・メトリクス | `PVTI_lAHOAVzM6c4BAoYLzgd90dM` |
| 4.4.2 | #115 | AlertManager・通知システム | `PVTI_lAHOAVzM6c4BAoYLzgd90dg` |
| 4.4.3 | #116 | BackupManager実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90ds` |
| 4.4.4 | #117 | PrivacyManager・セキュリティ強化 | `PVTI_lAHOAVzM6c4BAoYLzgd90dw` |
| 4.4.5 | #118 | 統合テスト・品質検証 | `PVTI_lAHOAVzM6c4BAoYLzgd90d4` |
| 4.4.6 | #119 | ドキュメント・リリース準備 | `PVTI_lAHOAVzM6c4BAoYLzgd90d8` |
| 4.5.1 | #120 | /edit コマンド実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90eE` |
| 4.5.2 | #121 | /review コマンド群実装 | `PVTI_lAHOAVzM6c4BAoYLzgd90eQ` |

## Usage Examples

### Task 4.1.1開始時
```bash
# ブランチ作成
git checkout -b refactor/service-container-phase4

# ステータス更新: Todo → In Progress
gh project item-edit --id "PVTI_lAHOAVzM6c4BAoYLzgd90Rw" \
  --field-id "PVTSSF_lAHOAVzM6c4BAoYLzgzYKtg" \
  --single-select-option-id "47fc9ee4" \
  --project-id "PVT_kwHOAVzM6c4BAoYL"
```

### Task 4.1.1完了時
```bash
# PRマージ後
# ステータス更新: In Progress → Done
gh project item-edit --id "PVTI_lAHOAVzM6c4BAoYLzgd90Rw" \
  --field-id "PVTSSF_lAHOAVzM6c4BAoYLzgzYKtg" \
  --single-select-option-id "98236657" \
  --project-id "PVT_kwHOAVzM6c4BAoYL"
```

## 注意事項

1. **必須操作**: ブランチ作成時のTodo→In Progress、PRマージ時のIn Progress→Done
2. **代替方法**: GitHub UI上でプロジェクトボードのドラッグ&ドロップも利用可能
3. **Project Item ID**: 各IssueごとにユニークなID。変更されることは基本的にない
4. **自動化**: 将来的にGitHub Actionsで自動化を検討

---

**作成日**: 2025-08-24
**対象**: Phase 4 PKM機能開発 (Issue #95-121)
