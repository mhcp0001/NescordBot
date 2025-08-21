# テキストメッセージ処理機能開発 - 2025-08-21

## 概要
Discord のテキストメッセージを Fleeting Note 形式で GitHub リポジトリの Obsidian vault に保存する機能の設計・実装計画。

## 1. 要求仕様

### 機能要件
- Discord テキストメッセージを Fleeting Note として保存
- `/note` Slash Command でテキスト処理起動
- `!note` プレフィックスでメッセージ処理
- GPT-3.5-turbo による整形・要約処理
- Obsidian vault 仕様準拠の Fleeting Note 形式
- GitHub リポジトリへの自動同期

### 非機能要件
- 応答時間: 3秒以内（初期応答）
- 最大テキスト長: 4000文字
- 同時処理: 最大10件/分
- 既存資産活用率: 85%以上

## 2. 設計概要

### アーキテクチャ
```
Discord User
    ↓
Voice Cog (拡張)
    ├── handle_text_message() - 新規
    ├── _format_fleeting_note() - 新規
    ├── process_with_ai() - 既存再利用
    └── /note command - 新規
    ↓
FleetingNoteView (TranscriptionView拡張)
    ↓
ObsidianGitHubService (Phase 3実装済み)
    ↓
GitHub Repository (Obsidian vault)
```

### Fleeting Note 形式
```markdown
---
id: 20250821153045
title: "要約テキスト..."
type: fleeting_note
status: fleeting
tags:
  - capture/
  - discord/
  - discord/text
context: "Discord #general でのテキストメッセージ"
source: "Discord Bot NescordBot"
created: 2025-08-21 15:30
---

# タイトル

## 💭 アイデア・思考の断片
[GPT処理済みテキスト]

## 🔗 関連しそうなこと
-

## ❓ 疑問・調べたいこと
-

## 📝 次のアクション
- [ ] Literature Noteに発展させる
- [ ] Permanent Noteに昇華する
- [ ] 関連資料を調査する
- [ ] アーカイブする

---

### Discord情報
- **サーバー**: サーバー名
- **チャンネル**: チャンネル名
- **ユーザー**: ユーザー名
- **メッセージID**: 1234567890
- **タイプ**: テキストメッセージ

---
*素早く記録することを優先。後で整理・発展させる。*
```

### ファイル名規則
`YYYYMMDD_HHMM_discord_text_[user_name].md`

### 保存先
`Fleeting Notes/` ディレクトリ

## 3. 実装タスク（GitHub Issue管理）

### Task 3.8: テキストメッセージ処理機能 - メインタスク
- **Issue**: #72
- **Project**: Nescord Project 登録済み
- **設計書**: docs/design/text_message_fleeting_note.md

### サブタスク
1. **Task 3.8.1**: Voice Cog基盤準備 - Issue #73
2. **Task 3.8.2**: テキストメッセージ処理実装 - Issue #74
3. **Task 3.8.3**: Slash Command実装 - Issue #75
4. **Task 3.8.4**: FleetingNoteView実装 - Issue #76
5. **Task 3.8.5**: テスト実装 - Issue #77

### 推定作業時間
- 総時間: 15時間（2-3日）
- 既存資産活用により大幅な時間短縮

## 4. 技術スタック

### 依存ライブラリ
- discord.py 2.3+ (既存)
- openai v1.99.9 (既存)
- pyyaml (新規追加)
- aiosqlite (既存)

### 既存コンポーネント活用
- `process_with_ai()`: GPT処理メソッド
- `TranscriptionView`: UI基盤クラス
- `ObsidianGitHubService`: GitHub保存サービス
- `SecurityValidator`: 入力検証
- `BatchProcessor`: バッチ処理

## 5. 実装上の重要ポイント

### 既存コードとの整合性
- process_with_aiメソッドは変更せず再利用
- TranscriptionViewの基本構造を維持
- ObsidianGitHubServiceのインターフェース維持

### セキュリティ
- SecurityValidatorによる入力検証
- ファイル名サニタイズ処理
- XSS・インジェクション攻撃対策

### エラーハンドリング
- OpenAI APIレート制限対応
- GitHub API障害時のローカルキューイング
- ユーザーフレンドリーなエラーメッセージ

## 6. テスト戦略

### 単体テスト
- test_text_message.py
- カバレッジ目標: 70%以上

### 統合テスト
- テキスト入力→GitHub保存の全フロー
- Fleeting Note仕様準拠検証
- 並行処理テスト

## 7. 前提条件

### 完了済みタスク（Phase 3.7）
- ✅ Task 3.7.1: SecurityValidator + BotConfig拡張（Issue #48）
- ✅ Task 3.7.2: Git操作層実装（Issue #49）
- 🔄 Task 3.7.3-3.7.5: 進行中

### 開発開始条件
Phase 3.7.5（ObsidianGitHubService統合テスト）の完了が必要

## 8. ドキュメント

### 作成済み
- docs/design/text_message_fleeting_note.md - 詳細設計書
- docs/operations/tasks.md - タスク管理（最新版）
- .tmp/requirements.md - 要求仕様書（作業用）
- .tmp/tasks.md - タスク詳細（作業用）

### GitHub管理
- Issue #72-#77: タスク管理
- Nescord Project: プロジェクトボード

## 9. 次のアクション

1. Phase 3.7.5の完了待ち
2. Task 3.8.1（Voice Cog基盤準備）から開始
3. ブランチ: `refactor/voice-cog-foundation`
4. 依存関係追加: `poetry add pyyaml`

---
*作成日: 2025-08-21*
*作成者: Claude Code*
*プロジェクト: NescordBot*
