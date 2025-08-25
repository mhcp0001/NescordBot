# Development Documentation

NescordBotの開発プロセスとワークフローに関する文書です。

## 🛠️ 開発ガイド

### [improved_workflow.md](./improved_workflow.md)
改善されたワークフロー
- GitHub Issue自動化ワークフロー
- ブランチ戦略
- PR管理プロセス

## 🚀 開発環境セットアップ

### 基本要件
- Python 3.11+
- Poetry (依存関係管理)
- Git
- GitHub CLI (推奨)

### セットアップ手順
```bash
# リポジトリクローン
git clone https://github.com/your-username/NescordBot.git
cd NescordBot

# 依存関係インストール
poetry install

# 環境変数設定
cp .env.example .env
# .envファイルを編集して必要な値を設定

# テスト実行
poetry run pytest tests/ -n auto -v
```

## 📋 開発ワークフロー

### 1. Issue作成
```bash
gh issue create --template feature_request.md --title "Description"
```

### 2. ブランチ作成 & 開発開始
```bash
gh issue develop 123 --name "type/123-description" --base main
```

### 3. PR作成（自動クローズ）
```bash
gh pr create --fill --web  # "Closes #123" を含める
```

### 4. 自動マージ設定
```bash
gh pr merge --auto --squash --delete-branch
```

## ✅ 品質基準

- **テストカバレッジ**: 78%以上維持
- **CI/CD成功率**: 100%
- **コード品質**: black, mypy, isort, flake8による自動チェック
- **セキュリティ**: 定期的な依存関係脆弱性監査

---

詳細な開発ガイドラインについては、各文書を参照してください。
