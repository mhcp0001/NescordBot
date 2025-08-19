# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## Top-Level Rules

- To maximize efficiency, **if you need to execute multiple independent processes, invoke those tools concurrently, not sequentially**.
- **You must think exclusively in English**. However, you are required to **respond in Japanese**.
- For temporary notes for design, create a markdown in `.tmp` and save it.
- **After using Write or Edit tools, ALWAYS verify the actual file contents using the Read tool**, regardless of what the system-reminder says. The system-reminder may incorrectly show "(no content)" even when the file has been successfully written.
- Please respond critically and without pandering to my opinions, but please don't be forceful in your criticism.


## Git Commit Rules

- **Create commits frequently**: Create a commit for each logical unit of change
- **Commit message format**: Follow conventional commits format (feat:, fix:, docs:, style:, refactor:, test:, chore:)
- **Atomic commits**: Each commit should represent a single, complete change
- **Test before commit**: Ensure the code builds and tests pass before committing
- **Include Co-Authored-By**: Always include the Claude signature in commit messages

### Commit Examples
- `feat: add user authentication` - New feature
- `fix: resolve null pointer exception in user service` - Bug fix
- `docs: update API documentation` - Documentation only
- `style: format code according to style guide` - Code style changes
- `refactor: extract validation logic into separate module` - Code refactoring
- `test: add unit tests for user service` - Adding tests
- `chore: update dependencies` - Maintenance tasks

## GitHub Issue and Project Management Rules (Automated Workflow)

### Prerequisites and Setup

#### GitHub CLI Installation and Authentication
Before using the automated workflow, ensure gh CLI is properly set up:

1. **Install GitHub CLI**
   ```bash
   # Windows (with Scoop)
   scoop install gh

   # macOS
   brew install gh

   # Linux/WSL
   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
   sudo apt update && sudo apt install gh
   ```

2. **Authenticate with GitHub**
   ```bash
   gh auth login
   # Select: GitHub.com
   # Select: HTTPS
   # Authenticate via: Browser (recommended)
   # Ensure you have 'repo' and 'workflow' scopes
   ```

3. **Verify Authentication**
   ```bash
   gh auth status
   # Should show: "Logged in to github.com as YOUR_USERNAME"
   ```

#### Repository Configuration Requirements
- **Enable auto-merge**: Repository Settings → General → Pull Requests → Allow auto-merge
- **Branch protection**: Settings → Branches → Add rule for `main`
  - Require status checks: `test`, `security`, `integration-test`
  - Require branches to be up to date before merging
- **Required permissions**: Write access to repository for general development

### Core Principles
- **1 Issue = 1 Branch = 1 PR**: Every task starts with an issue and ends with automated closure
- **Automation First**: Leverage gh CLI and GitHub features to minimize manual work
- **Template-Driven**: Use standardized templates for consistency and completeness
- **Auto-Linking**: Automatic connection between branches, commits, PRs, and issues

### Automated Issue Workflow

#### 1. Issue Creation
```bash
# Use templates for consistent reporting
gh issue create --template bug_report.md --title "Description"
gh issue create --template feature_request.md --title "Description"
```

#### 2. Branch Creation & Development Start
```bash
# Automatic branch creation with issue linking
gh issue develop 123 --name "type/123-description" --base main
# Types: feature/, fix/, docs/, refactor/, test/, ci/, hotfix/
```

#### 3. Commit Convention (Enhanced)
```bash
# Format: type: description (refs #NUMBER)

# Single line commit
git commit -m "feat: 新しい管理コマンドを実装 (refs #123)"

# Multi-line commit (using editor)
git commit  # Opens default editor for detailed message

# Multi-line commit (using heredoc)
git commit -F- <<EOF
feat: 新しい管理コマンドを実装 (refs #123)

- Slash commandの追加
- エラーハンドリングの改善
- ログ機能の統合
EOF
```

#### 4. PR Creation with Auto-Close
```bash
# Use template with automatic issue closure
gh pr create --fill --web
# Ensure PR body contains: "Closes #123"
```

#### 5. Automated Merge & Closure
```bash
# Enable auto-merge after CI passes
gh pr merge --auto --squash --delete-branch
# Results in: PR merged → Issue closed → Branch deleted → Project updated
```

### Branch Naming Convention
- **Format**: `type/issue-number-description`
- **Examples**:
  - `feature/123-admin-commands`
  - `fix/456-voice-api-error`
  - `docs/789-update-readme`

### Commit Message Standard (厳格化)
- **Format**: `type(scope): description (refs #issue-number)` **（Issue参照必須）**
- **Types**: feat, fix, docs, style, refactor, test, chore
- **Scope**: Optional module name (e.g., github, voice, admin)
- **Language**: Japanese description with English type prefix
- **Issue参照**: すべてのコミットに `(refs #issue-number)` を含める（例外なし）
- **Auto-linking**: `(refs #123)` creates automatic GitHub links

#### 例
```bash
feat(github): GitHub API統合の基本実装 (refs #51)
fix(voice): 音声処理のタイムアウト問題を修正 (refs #52)
docs: Phase 3タスクリストを更新 (refs #53)
test(admin): 管理者権限テストを追加 (refs #54)
```

### PR Requirements (強化)
- **Title**: Match commit convention (`type(scope): description`)
- **Body**: Must include `Closes #issue-number` for auto-closure **（必須）**
- **Template**: Use provided PR template for comprehensive information
- **Labels**: Auto-assigned based on branch type
- **Validation**: GitHub Actions will verify Issue reference in commits and PR body

#### PR作成時の必須チェック項目
1. すべてのコミットに `(refs #issue-number)` が含まれているか
2. PR本文に `Closes #issue-number` が含まれているか
3. CI/CDテストが全て成功しているか
4. コードレビューが完了しているか

### GitHub Features Integration

#### Templates Location
- Bug reports: `.github/ISSUE_TEMPLATE/bug_report.md`
- Feature requests: `.github/ISSUE_TEMPLATE/feature_request.md`
- Pull requests: `.github/pull_request_template.md`

#### Projects Integration
- **Board**: Todo → In Progress → Done
- **Auto-movement**: Issue creation → Todo, PR creation → In Progress, PR merge → Done
- **Tracking**: `gh project item-list PROJECT_NUMBER --owner @me`

#### Label Strategy
- **Type**: `bug`, `feature`, `documentation`, `refactor`, `chore`
- **Priority**: `priority: high`, `priority: medium`, `priority: low`
- **Status**: `good first issue`, `help wanted`, `needs-review`

### Claude Code Integration Commands

#### Task Selection
```bash
# List available issues
gh issue list --label "help wanted" --state open
gh issue view 123  # Detailed view
```

#### Development Flow
```bash
# 1. Start work
gh issue develop 123 --name "feature/123-new-command" --base main

# 2. Quality checks
poetry run pytest && poetry run black src/ && poetry run mypy src/

# 3. Create PR
git push && gh pr create --fill --web

# 4. Auto-merge setup
gh pr merge --auto --squash --delete-branch
```

### Error Handling and Troubleshooting

#### Common Issues and Solutions

1. **`gh issue develop` fails**
   - **Error**: "Issue not found" → Check issue number: `gh issue list`
   - **Error**: "Permission denied" → Re-authenticate: `gh auth refresh`
   - **Error**: "Branch already exists" → Use different name or delete old branch

2. **Quality checks fail locally**
   ```bash
   # Fix formatting issues
   poetry run black src/ --diff  # See what will change
   poetry run black src/         # Apply changes

   # Fix type issues
   poetry run mypy src/ --show-error-codes

   # Fix import sorting
   poetry run isort src/ --diff
   poetry run isort src/
   ```

3. **CI/GitHub Actions failures**
   - Check PR "Checks" tab for detailed logs
   - Common fixes:
     ```bash
     # Update dependencies
     poetry update

     # Regenerate lock file
     poetry lock --no-update

     # Clear cache and reinstall
     poetry cache clear pypi --all
     poetry install
     ```

4. **Merge conflicts**
   ```bash
   # Update your branch with latest main
   git fetch origin main
   git rebase origin/main  # Preferred method
   # OR
   git merge origin/main   # Alternative method

   # Resolve conflicts, then
   git add .
   git rebase --continue  # If rebasing
   git commit            # If merging
   git push --force-with-lease  # If rebased
   ```

5. **Auto-merge not working**
   - Ensure all required status checks pass
   - Check for merge conflicts: `gh pr status`
   - Verify branch protection settings
   - Manual fallback: `gh pr merge --squash --delete-branch`

#### Project Number Discovery
```bash
# Find project number for automation
gh project list --owner @me
# OR for organization
gh project list --owner ORG_NAME
```

### Quality Assurance (厳格化)
- **MANDATORY**: All PRs must pass CI/CD checks
- **MANDATORY**: Include test results in PR description
- **MANDATORY**: Use `Closes #number` in PR body for auto-closure
- **MANDATORY**: All commits must include `(refs #issue-number)` - no exceptions
- **MANDATORY**: Pre-commit hooks must pass (commit message validation)
- **MANDATORY**: GitHub Actions PR validation must pass
- **RECOMMENDED**: Enable auto-merge for streamlined workflow

### Pre-commit Hooks Integration
- **Installation**: `poetry add --group dev pre-commit`
- **Setup**: `pre-commit install --hook-type commit-msg`
- **Validation**: Automatic commit message format checking
- **Bypass**: Not allowed - all commits must follow the standard

### Migration Benefits
- **70% time reduction** in issue management tasks
- **Automatic synchronization** between all GitHub components
- **Consistent formatting** through templates
- **Zero manual issue closure** through automation
- **Enhanced traceability** through auto-linking

## [GLOBAL DIRECTIVE] Gemini Integration (Priority over project-specific CLAUDE.md)

### Trinity Principle for Knowledge Work

Maximize the quality and speed of intellectual production by combining human **decision-making**, Claude's **thought organization and execution**, and Gemini's **research and advisory** capabilities.

* **Human (User)**: The **decision-maker** who defines task objectives, requirements, and final goals, making ultimate decisions.
    * Capable of setting abstract goals but less adept at breaking them down into concrete tasks or systematic information organization.
* **Claude (You)**: The **primary facilitator** who understands user intent, structures thinking, and handles task decomposition, management, and execution.
    * Excels at following instructions methodically and executing tasks systematically, but has limited access to external real-time information and objective multi-perspective validation.
* **Gemini**: The **specialist advisor** providing access to current and comprehensive information through web search, expert knowledge, and diverse perspectives.
    * Strong at granular information gathering, fact-checking, and objective analysis, but not designed to understand overall task context or drive plans autonomously.

### Basic Workflow

1. **PROMPT Generation**
   Claude consolidates user requirements into a single text and stores it in environment variable `$PROMPT`

2. **Gemini CLI Invocation**
```bash
gemini <<EOF
$PROMPT
EOF
```
3. **Result Integration**
    Present Gemini's response
    Add Claude's additional analysis and commentary

### Collaboration Protocol (Revised: Claude-Led Second Opinion Approach)
#### Phase 1: Claude-Led Thought Organization & Analysis
* Begin with thorough consideration and hypothesis formation by Claude
* Organize task requirements, consider approaches, break down challenges, and create a clear thinking framework
* Clearly distinguish between your analysis results and areas requiring clarification or verification

#### Phase 2: Requesting Gemini's Second Opinion

* Consult Gemini based on Claude's analysis in these cases:
  * Gathering current/specialized information requiring search capabilities
  * Multi-perspective validation needed for analyses or judgments
  * Objective validity checks required for strategies or plans
  * Idea brainstorming or expanding creative thinking
* Present specific questions and verification points when consulting Gemini

#### Phase 3: Integration and Final Judgment
* Utilize Gemini's responses as a second opinion and integrate with Claude's analysis
* Formulate final judgments and recommendations aligned with user intent
* Critically evaluate Gemini's information rather than accepting it uncritically

### Primary Use Cases
1. Information Gathering & Research: Collect current, specialized, or niche information that Claude cannot access independently.
   * Example: "Research the latest AI market trends, including major players and technology developments"

2. Assumption & Strategy Validation: Verify the validity of task assumptions and approaches from an objective perspective.
   * Example: "Confirm whether this analytical approach can achieve our initial objectives and identify any potential concerns"

3. Idea Brainstorming: Obtain multi-perspective feedback on new plans or ideas to expand creative thinking.
   * Example: "Suggest additional approaches for our internal communication enhancement event proposal"

4. Structure & Planning Development: Create outlines and structural frameworks for reports, presentations, and projects.
    * Example: "Help develop a new service proposal by identifying necessary components and creating a draft structure"

5. Problem Analysis & Solution Development: Analyze problem causes from multiple angles and explore a broad range of solution options.
   *  Example: "List potential factors causing workflow inefficiencies from tool, process, and cultural perspectives"

6. Document & Output Review: Review created documents, materials, and plans from an objective standpoint to identify improvements.
   *  Example: "Review this report draft and suggest improvements for better logic and persuasiveness"
7. Task Decomposition: Break down large, abstract tasks into executable concrete steps and create actionable plans.
   *  Example: "Decompose the 'competitive analysis report' task into specific work procedures"
8. Options Comparison: Compare pros and cons of multiple tools, methods, or strategies to select the most suitable option.
   *   Example: "Compare information sharing tools A and B for our team, considering both functionality and cost"
9.  Risk Assessment: Identify potential risks and issues associated with plans or decisions beforehand.
    *   Example: "Identify potential risks in executing this marketing campaign"
10. Existing Deliverable Validation: Re-evaluate past documents or plans from current perspectives and propose improvements.
    *   Example: "Review last year's business plan and identify areas needing adjustment for current market conditions"

## Programming Rules

- Avoid hard-coding values unless absolutely necessary.
- Do not use `any` or `unknown` types in TypeScript.
- You must not use a TypeScript `class` unless it is absolutely necessary (e.g., extending the `Error` class for custom error handling that requires `instanceof` checks).

## Development Style - Specification-Driven Development

### Overview

When receiving development tasks, please follow the 4-stage workflow below. This ensures requirement clarification, structured design, and efficient implementation.

### 4-Stage Workflow

#### Stage 1: Requirements

- Analyze user requests and convert them into clear functional requirements
- Document requirements in `.tmp/requirements.md`
- Use `/requirements` command for detailed template

#### Stage 2: Design

- Create technical design based on requirements
- Document design in `.tmp/design.md`
- Use `/design` command for detailed template
- **Enhanced Design Process** (learned from Enhanced PubMed MCP):
  - Phase 1: Initial design draft
  - Phase 2: External specification research (WebSearch/WebFetch)
  - Phase 3: Technical validation (Gemini multi-perspective verification)
  - Phase 4: Quantitative constraint analysis
  - Phase 5: Design refinement based on findings

#### Stage 3: Task List

- Break down design into implementable units
- Document in `.tmp/tasks.md`
- Use `/tasks` command for detailed template
- Manage major tasks with TodoWrite tool

#### Stage 4: Implementation

- Implement according to task list
- For each task:
  - Update task to in_progress using TodoWrite
  - Execute implementation and testing
  - Run lint and typecheck
  - Update task to completed using TodoWrite

### Workflow Commands

- `/spec` - Start the complete specification-driven development workflow
- `/requirements` - Execute Stage 1: Requirements only
- `/design` - Execute Stage 2: Design only (requires requirements)
- `/tasks` - Execute Stage 3: Task breakdown only (requires design)

## Project Overview

NescordBot is a Discord bot built with Python that provides voice transcription and AI-powered features. It uses OpenAI's Whisper API for voice-to-text conversion and GPT models for text processing and summarization.

## Key Commands

### Running the Bot
```bash
# Using Poetry (preferred) - New module-based approach
poetry run python -m nescordbot

# Alternative module execution
poetry run python src/nescordbot/__main__.py

# Alternative if Poetry shell is activated
poetry shell
python -m nescordbot
```

### Development Commands
```bash
# Install dependencies with Poetry
poetry install

# Code formatting
poetry run black src/

# Linting
poetry run flake8 src/

# Type checking
poetry run mypy src/

# Import sorting
poetry run isort src/

# Run tests (with parallel execution)
poetry run pytest tests/ -n auto
poetry run pytest tests/ --cov=src --cov-report=html -n auto  # With coverage
poetry run pytest tests/ -m "not slow and not network" -n auto  # CI-style
```

### Dependency Management
```bash
# Add new package
poetry add package-name

# Add development package
poetry add --group dev package-name

# Update dependencies
poetry update

# Export to requirements.txt (for compatibility)
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

## Architecture

### Core Structure
- **src/nescordbot/**: Main package directory
  - **bot.py**: NescordBot class that extends commands.Bot
  - **main.py**: BotRunner and service management
  - **__main__.py**: Module entry point
  - **config.py**: Configuration management with Pydantic
  - **logger.py**: Logging service setup

- **Services Layer**: Data persistence and external integrations
  - **services/database.py**: DatabaseService with aiosqlite
  - **services/__init__.py**: Service container and dependency injection

- **Cogs System**: Modular command groups loaded dynamically
  - **cogs/general.py**: General commands (/help, /status, /ping)
  - **cogs/admin.py**: Administrative commands (/logs, /config, /dbstats)
  - **cogs/voice.py**: Voice processing with OpenAI Whisper transcription and GPT processing

### Key Technologies
- **discord.py 2.3+**: Discord API wrapper
- **OpenAI API**: Whisper for transcription, GPT-3.5/GPT-4 for text processing
- **aiosqlite**: Async SQLite database operations
- **Poetry**: Dependency management and virtual environment
- **pytest + pytest-xdist**: Parallel testing framework
- **asyncio**: Asynchronous operations throughout

### Event Flow for Voice Messages
1. User sends voice message → bot.py detects audio attachment
2. Downloads audio to temp file in data/ directory
3. Passes to voice.py cog for transcription via OpenAI Whisper
4. Processes transcription with GPT for formatting and summarization
5. Returns formatted result with interactive buttons (Obsidian save, X post - both pending implementation)
6. Cleans up temp files

### Environment Variables Required
- `DISCORD_TOKEN`: Bot authentication token
- `OPENAI_API_KEY`: For Whisper transcription and GPT processing
- Optional: `LOG_LEVEL`, `MAX_AUDIO_SIZE_MB`, `SPEECH_LANGUAGE`

## Testing Approach
- Uses pytest with pytest-asyncio for async testing
- **pytest-xdist**: Parallel test execution with `-n auto`
- Mock-based testing for Discord interactions
- Test files in tests/ directory mirror src/nescordbot/ structure
- **Coverage target**: 60%+ (currently 78%)
- **CI/CD**: GitHub Actions with Python 3.11/3.12 matrix

## Important Notes
- Bot requires FFmpeg installed for audio processing
- Poetry is the primary dependency manager (pyproject.toml)
- Supports deployment to Railway, AWS/GCP, Docker
- Audio files temporarily stored in data/ directory during processing
- Maximum audio file size: 25MB default
- Logging outputs to both console and bot.log file

## 最新セッション情報 (2025-08-19)

### 🎉 Task 3.7.1-3.7.2 完了報告
- **Task 3.7.1** (Issue #48): ✅ 完全完了 - SecurityValidator + BotConfig拡張実装
- **Task 3.7.2** (Issue #49): ✅ 完全完了 - Git操作層実装 (並行完了)
- **PR #55**: ✅ マージ完了、Issue自動クローズ
- **開発フロー改善**: ✅ 新ワークフロー文書化完了

### 🚀 次フェーズの開発対象
残りのPhase 3タスク：
- **Issue #50**: Task 3.7.3 - キュー永続化実装
- **Issue #51**: Task 3.7.4 - 認証とバッチ処理実装
- **Issue #52**: Task 3.7.5 - 統合テスト実装

### 📋 今セッションの主要成果

#### 実装完了項目
- ✅ **SecurityValidatorクラス**: XSS・インジェクション攻撃検出、ファイルパス検証
- ✅ **BotConfig拡張**: GitHub設定統合、複数インスタンス対応
- ✅ **GitOperationServiceクラス**: 安全なGit操作、バッチ処理キュー機能
- ✅ **包括的テストスイート**: 78%カバレッジ維持、CI/CD完全通過

#### 問題解決実績
- ✅ **pathvalidate依存関係欠落問題**: リベース時の依存関係復元を完全解決
- ✅ **Git操作テスト失敗**: Gemini協力によりモック設定問題を特定・修正
- ✅ **非同期テスト不安定性**: タイムアウト処理とクリーンアップ改善で安定化

#### ワークフロー改善
- ✅ **改善された開発フロー文書**: `docs/development/improved_workflow.md` 作成
- ✅ **PR検証ルール強化**: コミットメッセージ長制限、形式厳密化
- ✅ **Claude-Gemini協力パターン**: 技術問題解決の効率的手法確立

### 🛠️ 技術スタック確立状況
```
✅ SecurityValidator    - セキュリティ基盤
✅ BotConfig           - 設定管理拡張
✅ GitOperationService - Git操作安全化
✅ DatabaseService     - SQLite URL対応
✅ CI/CDパイプライン    - 完全自動化
```

### 📖 重要な学習成果
- **問題解決協力**: Claude+Gemini の効果的な協力パターン
- **段階的修正**: 複数問題を順次解決する systematic approach
- **証拠ベース判断**: ログとテスト結果に基づく確実な問題特定
- **品質維持**: 機能追加時のテストカバレッジ維持戦略

### 📋 次セッション開始ガイド
1. **Task 3.7.3開始**: Issue #50 - キュー永続化機能
2. **ブランチ**: `feature/50-queue-persistence` 推奨
3. **設計参照**: `docs/design/obsidian_github_integration.md`
4. **ワークフロー**: `docs/development/improved_workflow.md` 参照
