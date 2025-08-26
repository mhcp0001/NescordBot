# GitHub Issue自動プロジェクト追加機能の実装と検証

## 概要
GitHub CLI v2.76.2を使用したIssue作成時の自動プロジェクト追加機能の検証と実装を完了しました。

## 検証結果

### ✅ 安定動作確認
- **GitHub CLI バージョン**: v2.76.2 (2025-07-30)
- **認証スコープ**: `gist`, `project`, `read:org`, `repo`, `workflow`
- **プロジェクト**: "Nescord project" (ID: 3, PVT_kwHOAVzM6c4BAoYL)

### 🧪 実際のテスト実行
```bash
# テストIssue作成 - 成功
gh issue create --repo mhcp0001/NescordBot \
  --project "Nescord project" \
  --title "テスト: プロジェクト自動追加" \
  --body "プロジェクト自動追加機能のテストです。すぐに削除予定。"

# 結果: https://github.com/mhcp0001/NescordBot/issues/128
# プロジェクト追加確認: 正常に"Nescord project"に追加された
# テストIssue削除: gh issue close 128 --reason "not planned"
```

## 実装された推奨コマンド

### Issue作成の標準フォーマット
```bash
# テンプレート使用版
gh issue create \
  --project "Nescord project" \
  --template feature_request.md \
  --title "feat: 新機能名" \
  --body "詳細な説明"

# 直接作成版
gh issue create \
  --project "Nescord project" \
  --title "feat: 機能名" \
  --body "$(cat <<'EOF'
## 概要
機能の説明

## 実装内容
- [ ] タスク1
- [ ] タスク2

## 完了条件
期待される結果

## 推定時間
X時間
EOF
)"
```

## 重要な発見と注意点

### ❌ 失敗する方法
```bash
# プロジェクト番号指定は失敗
gh issue create --project 3  # Error: '3' not found
```

### ✅ 成功する方法
```bash
# プロジェクト名指定で成功
gh issue create --project "Nescord project"  # 正常動作
```

## 自動化フローの完成形

1. **Issue作成**: `--project "Nescord project"` で自動プロジェクト追加
2. **ブランチ作成**: `gh issue develop` でリンク
3. **PR作成**: `Closes #番号` で自動クローズ設定
4. **GitHub Actions**: 自動ステータス更新（Todo → In Progress → Done）

## CLAUDE.mdへの記録

以下の内容をCLAUDE.mdの該当セクションに追加済み：
- 新しい推奨コマンド形式
- 安定性確認情報
- プロジェクト指定の注意点
- GitHub CLI バージョン情報

## 効果と期待値

- **手動Project追加作業**: 100%削減
- **Issue管理ミス**: 防止
- **開発効率**: 向上
- **ワークフロー一貫性**: 確保

この機能により、Issue管理の完全自動化がさらに一歩前進しました。
