# NescordBot Development Commands

.PHONY: help check format lint type test install clean ci pre-commit

# Default target
help:  ## 使用可能なコマンドを表示
	@echo "🤖 NescordBot Development Commands"
	@echo "================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## 依存関係をインストール
	poetry install
	poetry run pre-commit install

check:  ## 全品質チェック (CI相当)
	@echo "🔍 Running all quality checks..."
	poetry run black --check src/ tests/
	poetry run isort --check-only src/ tests/
	poetry run ruff check src/ tests/
	poetry run mypy src/ --ignore-missing-imports
	@echo "✅ All checks passed!"

format:  ## コードフォーマット自動修正
	@echo "🔧 Formatting code..."
	poetry run black src/ tests/
	poetry run isort src/ tests/
	poetry run ruff check --fix src/ tests/
	@echo "✅ Code formatted!"

lint:  ## Lintチェックのみ
	@echo "🔍 Running lint checks..."
	poetry run ruff check src/ tests/

type:  ## 型チェック
	@echo "🔍 Running type checks..."
	poetry run mypy src/ --ignore-missing-imports

test:  ## テスト実行
	@echo "🧪 Running tests..."
	poetry run pytest tests/ -v --cov=src

test-quick:  ## 高速テスト (slow除外)
	@echo "🧪 Running quick tests..."
	poetry run pytest tests/ -v -m "not slow and not network"

ci:  ## CI環境での全チェック
	@echo "🚀 Running CI checks..."
	poetry run black --check src/ tests/
	poetry run isort --check-only src/ tests/ 
	poetry run ruff check src/ tests/
	poetry run mypy src/ --ignore-missing-imports
	poetry run pytest tests/ -v --cov=src -m "not slow and not network"
	@echo "✅ CI checks completed!"

pre-commit:  ## pre-commitフック実行
	@echo "🔒 Running pre-commit hooks..."
	poetry run pre-commit run --all-files

clean:  ## キャッシュファイル削除
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	@echo "✅ Cache cleaned!"

dev:  ## 開発環境セットアップ
	@echo "🛠️  Setting up development environment..."
	poetry install
	poetry run pre-commit install
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "💡 使用方法:"
	@echo "  make check    - 全品質チェック"
	@echo "  make format   - コード自動修正"
	@echo "  make test     - テスト実行"
	@echo "  Ctrl+Shift+Q  - VS Code: クイックチェック"
	@echo "  Ctrl+Shift+F  - VS Code: 自動修正"

run:  ## Bot実行 (開発用)
	@echo "🚀 Starting NescordBot..."
	poetry run python run.py