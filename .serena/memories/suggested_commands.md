# NescordBot 推奨コマンド一覧

## 基本開発コマンド

### Bot実行
```bash
# Poetry環境でBot実行（推奨）
poetry run python -m nescordbot

# 代替モジュール実行
poetry run python src/nescordbot/__main__.py

# Poetry shell環境内で
poetry shell
python -m nescordbot
```

### 依存関係管理
```bash
# 初期セットアップ
poetry install

# パッケージ追加
poetry add package-name

# 開発用パッケージ追加
poetry add --group dev package-name

# 依存関係更新
poetry update

# requirements.txt生成（互換性）
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

## 品質管理・テスト

### Makefileコマンド（推奨）
```bash
# 開発環境セットアップ
make dev

# 全品質チェック（CI相当）
make check

# コード自動フォーマット
make format

# テスト実行（カバレッジ付き）
make test

# 高速テスト（slow・networkテスト除外）
make test-quick

# CI環境チェック
make ci

# pre-commitフック実行
make pre-commit

# キャッシュクリア
make clean
```

### 個別品質チェック
```bash
# コードフォーマット
poetry run black src/ tests/

# Import文ソート
poetry run isort src/ tests/

# Linting
poetry run ruff check src/ tests/

# 型チェック
poetry run mypy src/ --ignore-missing-imports

# テスト実行（並列）
poetry run pytest tests/ -n auto

# カバレッジ付きテスト
poetry run pytest tests/ --cov=src --cov-report=html -n auto

# CI用テスト（slow・network除外）
poetry run pytest tests/ -m "not slow and not network" -n auto
```

## GitHub統合ワークフロー

### Issue・PR自動化
```bash
# 利用可能Issue一覧
gh issue list --label "help wanted" --state open

# Issue詳細確認
gh issue view 123

# Issueから開発ブランチ作成
gh issue develop 123 --name "feature/123-description" --base main

# PR作成（自動Issue連携）
git push
gh pr create --fill --web

# 自動マージ設定（CI通過後）
gh pr merge --auto --squash --delete-branch
```

### コミット規約
```bash
# 標準フォーマット（Issue参照必須）
git commit -m "feat: 新機能実装 (refs #123)"
git commit -m "fix: バグ修正 (refs #124)"
git commit -m "docs: ドキュメント更新 (refs #125)"

# 複数行コミット
git commit -F- <<EOF
feat: 新しい管理コマンドを実装 (refs #123)

- Slash commandの追加
- エラーハンドリングの改善
- ログ機能の統合
EOF
```

## Windowsシステム用コマンド

### FFmpegインストール
```bash
# Chocolatey（推奨）
choco install ffmpeg

# Scoop
scoop install ffmpeg
```

### GitHub CLI
```bash
# Scoop
scoop install gh

# 認証
gh auth login
gh auth status
```

### ファイル操作
```bash
# ディレクトリ一覧
dir
ls  # WSL/PowerShell

# ファイル検索
where python
Get-Command python  # PowerShell

# プロセス管理
tasklist | findstr python
Stop-Process -Name python  # PowerShell
```

## 環境設定

### Poetry環境
```bash
# Poetry shell起動
poetry shell

# 仮想環境情報
poetry env info

# 仮想環境パス
poetry env info --path
```

### 環境変数設定
```bash
# .envファイル作成
cp .env.example .env

# 環境変数確認（PowerShell）
$env:DISCORD_TOKEN
$env:OPENAI_API_KEY
```

## デバッグ・ログ
```bash
# ログファイル確認
Get-Content bot.log -Tail 50  # PowerShell
type bot.log  # CMD

# リアルタイムログ監視（PowerShell）
Get-Content bot.log -Wait
```
