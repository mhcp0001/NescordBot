# NescordBot プロジェクト管理

## 📋 Issue駆動開発

このプロジェクトはGitHub Issue駆動で開発を進めています。

### 現在のステータス

- **Phase 1: MVP基盤** - 実装中 (Issues #2-#11)
  - Milestone: [Phase 1: MVP基盤](https://github.com/mhcp0001/NescordBot/milestone/1)
  - 期限: 2025年8月30日
  - 進捗: 0/10 完了

### Issueの構成

#### ラベル体系

**Phaseラベル**
- `Phase1` - MVP基盤（緑）
- `Phase2` - 開発基盤強化（青）
- `Phase3` - GitHub連携（紫）
- `Phase4` - 運用基盤（赤）

**優先度ラベル**
- `priority:critical` - 最優先（赤）
- `priority:high` - 高優先度（オレンジ）
- `priority:medium` - 中優先度（黄）
- `priority:low` - 低優先度（薄紫）

**カテゴリラベル**
- `setup` - 環境構築
- `feature` - 機能実装
- `test` - テスト
- `ci/cd` - CI/CD
- `deployment` - デプロイメント

### 開発フロー

1. **Issue選択**
   ```bash
   # 未着手のIssueをリスト
   gh issue list --label "Phase1" --state open
   ```

2. **ブランチ作成**
   ```bash
   # Issue番号でブランチ作成
   git checkout -b issue-2-project-setup
   ```

3. **実装**
   - Issueの要件に従って実装
   - タスクリストをチェック

4. **PR作成**
   ```bash
   # Issue番号を含むPR作成
   gh pr create --title "Fix #2: プロジェクト初期設定" --body "Closes #2"
   ```

5. **Issue完了**
   - PRマージ時に自動的にIssueがクローズされる

### コマンドリファレンス

```bash
# Phase 1の進捗確認
gh issue list --milestone "Phase 1: MVP基盤"

# 高優先度タスクの確認
gh issue list --label "priority:high" --state open

# 自分にアサインされたIssue
gh issue list --assignee @me

# Issueの詳細表示
gh issue view 2

# Issueのステータス更新
gh issue close 2
gh issue reopen 2

# ラベルの追加/削除
gh issue edit 2 --add-label "in-progress"
gh issue edit 2 --remove-label "in-progress"
```

### プロジェクトボード（Web UI）

GitHub上でプロジェクトボードを作成し、カンバン方式で管理することを推奨：

1. リポジトリの[Projects](https://github.com/mhcp0001/NescordBot/projects)タブへ
2. 「New project」をクリック
3. 「Board」テンプレートを選択
4. 以下のカラムを作成：
   - **Backlog** - 未着手
   - **In Progress** - 作業中
   - **Review** - レビュー待ち
   - **Done** - 完了

### 実装優先順位

#### Phase 1 (現在)

最優先:
1. Issue #2 - プロジェクト初期設定
2. Issue #3 - Poetry環境構築
3. Issue #4 - ConfigManager実装

高優先:
4. Issue #5 - LoggerService実装
5. Issue #6 - BotCore実装（**critical**）

中優先:
6. Issue #7 - GeneralCog実装
7. Issue #8 - 起動スクリプト作成
8. Issue #9 - テスト作成
9. Issue #10 - CI設定

低優先:
10. Issue #11 - Railway準備

### 進捗トラッキング

週次で以下を確認：
- [ ] 完了したIssue数
- [ ] 残タスク数
- [ ] ブロッカーの有無
- [ ] 次週の優先事項

### コミットメッセージ規約

Issue番号を必ず含める：
```
feat: #2 プロジェクト構造の初期設定

- src/, tests/, docs/ディレクトリ作成
- .env.exampleファイル追加
- .gitignore更新

Closes #2
```

### 今後のPhase計画

- **Phase 2**: 開発基盤強化（9月上旬）
- **Phase 3**: GitHub連携機能（9月中旬）
- **Phase 4**: 運用基盤完成（9月下旬）

各Phaseの開始時に、対応するIssueを一括作成します。
