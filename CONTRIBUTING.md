# コントリビューションガイド

NescordBot プロジェクトへの貢献に感謝します！このガイドでは、効率的で一貫性のある開発プロセスを確保するためのルールとワークフローを説明します。

## 📋 Issue ライフサイクル

当プロジェクトでは、以下の自動化されたIssueライフサイクルを採用しています：

### 1. Issue作成 → Todo ステータス
- Issueを作成すると**自動的にプロジェクトボードに追加**され、`Todo` ステータスに設定されます
- 適切なIssueテンプレートを選択し、必要な情報を記入してください

### 2. 開発開始 → In Progress ステータス
- ブランチ作成後、PRを作成すると**自動的に `In Progress` ステータス**に変更されます
- 手動でのステータス変更は不要です

### 3. CI通過 → Ready for Integration ステータス
- 全CIチェックが成功すると**自動的に `Ready for Integration` ステータス**に変更されます
- これによりコードレビューとマージの準備が完了したことを示します

### 4. マージ → Done ステータス & Issue クローズ
- PRがmainブランチにマージされると：
  - **関連Issueが自動的にクローズ**されます
  - プロジェクトボードで `Done` ステータスに変更されます

## 🌿 ブランチ命名規則

以下の命名規則に従ってブランチを作成してください：

```
<type>/<issue-number>-<short-description>
```

### タイプ一覧
- `feature/123-user-authentication` - 新機能追加
- `fix/456-login-bug` - バグ修正
- `docs/789-update-readme` - ドキュメント更新
- `refactor/101-cleanup-code` - コードリファクタリング
- `test/202-add-unit-tests` - テスト追加
- `chore/303-update-deps` - 依存関係更新・その他

### 例
```bash
git checkout -b feature/123-discord-slash-commands
git checkout -b fix/456-voice-processing-timeout
git checkout -b docs/789-api-documentation
```

## 🔗 Pull Request 作成ルール

### 必須要件
1. **Issue参照**: PRの説明文に必ず `Closes #<issue-number>` を含めてください
   ```markdown
   ## 概要
   音声メッセージ処理機能の実装

   ## 変更内容
   - 音声ファイルのアップロード処理
   - Whisper APIとの統合

   Closes #123
   ```

2. **CI通過**: 全てのCIチェック（テスト、Lint、型チェック等）が成功している必要があります

3. **PRテンプレート**: 提供されているPRテンプレートを適切に記入してください

### 推奨事項
- 小さく、レビューしやすいPRを心がける
- 関連する変更は1つのPRにまとめる
- 明確で分かりやすいPRタイトルとDescription

## 🚀 自動化システム

### GitHub Actions による自動処理

| イベント | 自動処理 | 説明 |
|---------|---------|------|
| Issue作成 | プロジェクトに自動追加 → `Todo` | Issue Automation |
| PR作成 | 関連Issueを `In Progress` に変更 | project-update.yml |
| CI成功 | PRを `Ready for Integration` に変更 | ci-success-update.yml |
| PRマージ | Issue自動クローズ → `Done` | GitHub標準機能 |

### 手動操作の禁止事項
以下の操作は**自動化されているため手動で行わないでください**：
- ❌ プロジェクトボードでのステータス手動変更
- ❌ Issueの手動クローズ（緊急時を除く）
- ❌ PRと無関係なIssueの操作

## 📝 コミットメッセージ規約

[Conventional Commits](https://www.conventionalcommits.org/) に準拠してください：

```
<type>(scope): <description> (refs #<issue-number>)

例:
feat(voice): 音声認識機能を実装 (refs #123)
fix(api): Whisper APIタイムアウト問題を修正 (refs #456)
docs: READMEにインストール手順を追加 (refs #789)
```

### Type 一覧
- `feat` - 新機能
- `fix` - バグ修正
- `docs` - ドキュメント更新
- `style` - コードスタイル変更
- `refactor` - コードリファクタリング
- `test` - テスト追加・修正
- `chore` - その他の変更

## 🔍 開発環境とテスト

### 開発環境セットアップ
```bash
# Poetry依存関係インストール
poetry install

# 開発用環境変数設定
cp .env.example .env
# .envファイルを適切に編集

# テスト実行
poetry run pytest
```

### コード品質チェック
提出前に以下のチェックを実行してください：
```bash
# フォーマット
poetry run black src/
poetry run isort src/

# Lint
poetry run flake8 src/

# 型チェック
poetry run mypy src/

# テスト
poetry run pytest tests/ -n auto
```

## 🛡️ セキュリティガイドライン

- APIキーや秘密情報をコミットに含めない
- 環境変数（`.env`）ファイルはリポジトリにプッシュしない
- セキュリティ脆弱性を発見した場合は、公開Issueではなく直接メンテナーに連絡

## 🤝 コードレビュー

### レビュアーのガイドライン
- 建設的なフィードバックを提供
- コードの動作、可読性、保守性を評価
- セキュリティとパフォーマンスの観点から確認

### PR作成者のガイドライン
- レビューコメントに迅速に対応
- 変更の理由を明確に説明
- 必要に応じて追加の説明や資料を提供

## 📞 サポート

ご質問や問題がある場合：
1. 既存のIssueを検索
2. 該当する内容がない場合は新しいIssueを作成
3. 緊急の場合はDiscussionを利用

---

この自動化システムにより、開発者は**実装に集中**でき、プロジェクト管理の負担が大幅に軽減されます。

**Happy Coding! 🎉**
