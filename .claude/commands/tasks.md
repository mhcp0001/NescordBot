---
allowed-tools: TodoWrite, TodoRead, Read, Write, MultiEdit
description: Break down design into implementable tasks with branch strategy (Stage 3 of Spec-Driven Development)
---

## Context

- Requirements: @.tmp/requirements.md
- Design document: @.tmp/design.md

## Your task

### 1. Verify prerequisites

- Check that both `.tmp/requirements.md` and `.tmp/design.md` exist
- If not, inform user to complete previous stages first

### 2. Analyze design document

Read and understand the design thoroughly to identify all implementation tasks

### 3. Create Task List Document and Branch Strategy

When creating tasks, you MUST also propose a branching strategy following GitHub Flow methodology.

For each task, automatically determine:
- Task type (feature, refactor, test, ci, docs, hotfix)
- Recommended branch name using format: `<type>/<short-description>`
- The `<short-description>` should be a kebab-case summary in English (5-7 words max)
- For complex tasks with multiple types, choose the primary work focus as the type

Create `.tmp/tasks.md` with the following structure:

```markdown
# タスクリスト - [機能/改善名]

## 概要

- 総タスク数: [数]
- 推定作業時間: [時間/日数]
- 優先度: [高/中/低]

## ブランチ戦略

本プロジェクトではGitHub Flowを採用しています：
- **1タスク = 1ブランチ = 1PR** の原則
- 全てのブランチは`main`から作成
- 依存関係のあるタスクは、依存先がmainにマージされてから作業開始

## タスク一覧とブランチ戦略

### Phase 1: 準備・調査

#### Task 1.1: [タスク名]

- [ ] [具体的な作業項目1]
- [ ] [具体的な作業項目2]
- [ ] [具体的な作業項目3]
- **完了条件**: [明確な完了条件]
- **依存**: [依存するタスク または なし]
- **推定時間**: [時間]
- **ブランチ**: `[type]/[kebab-case-description]`

#### Task 1.2: [タスク名]

- [ ] [具体的な作業項目1]
- [ ] [具体的な作業項目2]
- **完了条件**: [明確な完了条件]
- **依存**: [依存するタスク]
- **推定時間**: [時間]
- **ブランチ**: `[type]/[kebab-case-description]`

### Phase 2: 実装

#### Task 2.1: [機能名]の実装

- [ ] [実装項目1]
- [ ] [実装項目2]
- [ ] [実装項目3]
- **完了条件**: [明確な完了条件]
- **依存**: [依存するタスク]
- **推定時間**: [時間]
- **ブランチ**: `feature/[kebab-case-description]`

#### Task 2.2: [機能名]の実装

- [ ] [実装項目1]
- [ ] [実装項目2]
- **完了条件**: [明確な完了条件]
- **依存**: [依存するタスク]
- **推定時間**: [時間]
- **ブランチ**: `feature/[kebab-case-description]`

### Phase 3: 検証・テスト

#### Task 3.1: [検証項目]

- [ ] [テスト項目1]
- [ ] [テスト項目2]
- [ ] [テスト項目3]
- **完了条件**: [明確な完了条件]
- **依存**: [依存するタスク]
- **推定時間**: [時間]
- **ブランチ**: `test/[kebab-case-description]`

### Phase 4: 仕上げ

#### Task 4.1: [仕上げ項目]

- [ ] [仕上げ作業1]
- [ ] [仕上げ作業2]
- **完了条件**: [明確な完了条件]
- **依存**: [依存するタスク]
- **推定時間**: [時間]
- **ブランチ**: `[type]/[kebab-case-description]`

## 実装順序とブランチ戦略

1. **Phase 1から順次実行**
2. **並行実行可能なタスクは並行で実行**
3. **依存関係を考慮した実装順序**

### 依存関係のあるタスクのワークフロー

1. 全てのブランチは`main`の最新状態から作成
2. 依存先タスクのPRが`main`にマージされるまで待機
3. マージ後、作業ブランチで`git pull origin main`を実行
4. 最新の変更を取り込んでから開発開始

## ブランチ命名規則

- **feature/**: 新機能実装 (例: `feature/user-authentication`)
- **refactor/**: リファクタリング (例: `refactor/database-layer`)
- **test/**: テスト追加・改善 (例: `test/unit-auth-service`)
- **ci/**: CI/CD関連 (例: `ci/github-actions-setup`)
- **docs/**: ドキュメント (例: `docs/api-documentation`)
- **hotfix/**: 緊急修正 (例: `hotfix/security-vulnerability`)

## リスクと対策

- [特定されたリスク]: [対策方法]

## 注意事項

- 各タスクはコミット単位で完結させる
- タスク完了時は必要に応じて品質チェックを実行
- 不明点は実装前に確認する
- ブランチ作成前に依存関係を確認する
```

### 4. Register tasks in TodoWrite

Extract main tasks (Phase level or important tasks) and register them using TodoWrite tool with appropriate priorities

### 5. Create implementation guide

Add a section at the end of tasks.md:

```markdown
## 実装開始ガイド

### 開発ワークフロー
1. タスクリストに従って順次実装を進める
2. 各タスクの開始時にTodoWriteでin_progressに更新
3. 完了時はcompletedに更新
4. 問題発生時は速やかに報告

### ブランチ作成・運用手順
1. **ブランチ作成**: `git checkout -b [推奨ブランチ名] main`
2. **依存関係確認**: 依存タスクがmainにマージ済みか確認
3. **開発・コミット**: 頻繁に意味のあるコミットを作成
4. **PR作成**: 完了後はプルリクエストを作成
5. **マージ後**: 不要なローカルブランチを削除

### 注意事項
- 1タスク = 1ブランチ = 1PRの原則を遵守
- ブランチは短命に保つ（2-3日以内）
- 依存関係のあるタスクは順序を守る
```

### 6. Present to user

Show the task breakdown and:

- Explain the implementation order and branch strategy
- Highlight any critical paths and dependencies
- Present the recommended branching workflow
- Ask for approval to begin implementation

## Important Notes

- Tasks should be commit-sized (completable in 1-4 hours)
- Include clear completion criteria for each task
- Consider parallel execution opportunities
- Include testing tasks throughout, not just at the end
- Each task must have a specific branch name following GitHub Flow
- Analyze task content to determine appropriate branch type (feature/refactor/test/ci/docs/hotfix)
- Ensure branch names are descriptive and use kebab-case
- Keep branch names concise (5-7 words maximum in description)
- For tasks with multiple aspects, focus on the primary objective for type selection
- Consider adding issue number if working with GitHub Issues (e.g., feature/123-user-auth)

think hard
