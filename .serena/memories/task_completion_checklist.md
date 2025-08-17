# タスク完了時のチェックリスト

## 必須実行項目（順番厳守）

### 1. コード品質チェック
```bash
# 自動フォーマット適用
make format

# または個別実行
poetry run black src/ tests/
poetry run isort src/ tests/
poetry run ruff check --fix src/ tests/
```

### 2. 型チェック・Lint
```bash
# 全品質チェック（推奨）
make check

# または個別実行
poetry run mypy src/ --ignore-missing-imports
poetry run ruff check src/ tests/
```

### 3. テスト実行
```bash
# 全テスト（カバレッジ付き）
make test

# または高速テスト
make test-quick

# 個別実行
poetry run pytest tests/ -v --cov=src -n auto
```

### 4. pre-commitフック確認
```bash
# pre-commitフック実行
make pre-commit

# または直接実行
poetry run pre-commit run --all-files
```

## Git・GitHub統合（CLAUDE.md規約）

### 5. コミット作成
```bash
# コミットメッセージ形式（Issue参照必須）
git add .
git commit -m "feat: 新機能実装 (refs #123)"

# 複数行の場合
git commit -F- <<EOF
feat: 音声認識機能の改善 (refs #123)

- Whisper APIの応答時間改善
- エラーハンドリング強化
- ログ出力の詳細化
EOF
```

### 6. PR作成・マージ
```bash
# ブランチプッシュ
git push

# PR作成（自動Issue連携）
gh pr create --fill --web

# PR本文に "Closes #123" 含める（自動Issue閉鎖）

# 自動マージ設定（CI通過後）
gh pr merge --auto --squash --delete-branch
```

## CI/CD品質確認

### 7. GitHub Actions確認
- [ ] **pytest**: 全テスト通過
- [ ] **black**: コードフォーマット適合
- [ ] **ruff**: Lint問題なし
- [ ] **mypy**: 型エラーなし
- [ ] **security**: セキュリティスキャン通過

### 8. カバレッジ確認
```bash
# カバレッジレポート生成
poetry run pytest tests/ --cov=src --cov-report=html

# htmlcov/index.html でカバレッジ確認
# 目標: 60%以上（現在78%）
```

## エラー対処・トラブルシューティング

### 品質チェック失敗時
```bash
# フォーマットエラー
poetry run black src/ --diff  # 差分確認
poetry run black src/         # 自動修正

# 型エラー
poetry run mypy src/ --show-error-codes

# Import順序エラー
poetry run isort src/ --diff
poetry run isort src/
```

### テスト失敗時
```bash
# 詳細出力でテスト実行
poetry run pytest tests/ -v -s

# 特定テストのみ実行
poetry run pytest tests/test_voice_cog.py::test_transcribe -v

# キャッシュクリア後再実行
make clean
poetry run pytest tests/
```

### Merge conflict解決
```bash
# mainブランチの最新取得
git fetch origin main

# Rebase（推奨）
git rebase origin/main
# コンフリクト解決後
git add .
git rebase --continue
git push --force-with-lease

# または Merge
git merge origin/main
git add .
git commit
git push
```

## 最終確認項目

### 9. 動作確認
```bash
# Bot起動テスト
poetry run python -m nescordbot

# 主要機能テスト（手動）
# - /help コマンド
# - /status コマンド
# - 音声メッセージ処理
```

### 10. ドキュメント更新（必要時）
- [ ] README.md機能説明更新
- [ ] CLAUDE.md追加設定反映
- [ ] コメント・docstring追加

### 11. 依存関係管理
```bash
# 新パッケージ追加時
poetry add package-name

# requirements.txt更新（互換性）
poetry export -f requirements.txt --output requirements.txt --without-hashes

# poetry.lock更新
poetry lock --no-update
```

## 緊急時・Hotfix対応

### Critical Bug修正
```bash
# hotfixブランチ作成
git checkout main
git checkout -b hotfix/critical-bug-fix

# 修正・テスト
make check && make test

# 緊急マージ（レビュー短縮）
git push
gh pr create --title "hotfix: 緊急修正" --body "Closes #issue"
gh pr merge --squash --delete-branch  # 自動マージ無効化
```

### Rollback手順
```bash
# 前回コミットに戻す
git revert HEAD

# 特定コミットに戻す
git revert <commit-hash>

# 強制ロールバック（慎重に）
git reset --hard <previous-commit>
git push --force-with-lease
```
