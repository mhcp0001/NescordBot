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
git commit -m "feat: 新しい管理コマンドを実装 (refs #123)

- Slash commandの追加
- エラーハンドリングの改善
- ログ機能の統合"
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

### Commit Message Standard
- **Format**: `type: description (refs #issue-number)`
- **Types**: feat, fix, docs, style, refactor, test, chore
- **Language**: Japanese description with English type prefix
- **Auto-linking**: `(refs #123)` creates automatic GitHub links

### PR Requirements
- **Title**: Match commit convention (`type: description`)
- **Body**: Must include `Closes #issue-number` for auto-closure
- **Template**: Use provided PR template for comprehensive information
- **Labels**: Auto-assigned based on branch type

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

### Quality Assurance
- **MANDATORY**: All PRs must pass CI/CD checks
- **MANDATORY**: Include test results in PR description
- **MANDATORY**: Use `Closes #number` in PR body for auto-closure
- **RECOMMENDED**: Enable auto-merge for streamlined workflow

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
# Using Poetry (preferred)
poetry run python src/bot.py
# Or from run.py
poetry run python run.py

# Alternative if Poetry shell is activated
poetry shell
python src/bot.py
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

# Run tests
poetry run pytest tests/
poetry run pytest --cov=src tests/  # With coverage
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
- **src/bot.py**: Main bot entry point with NescordBot class that extends commands.Bot
  - Handles bot initialization, event listeners, and voice message detection
  - Manages cog loading and slash command synchronization

- **Cogs System**: Modular command groups loaded dynamically
  - **src/cogs/general.py**: General commands (/help, /status, /ping)
  - **src/cogs/voice.py**: Voice processing with OpenAI Whisper transcription and GPT processing

### Key Technologies
- **discord.py 2.3+**: Discord API wrapper
- **OpenAI API**: Whisper for transcription, GPT-3.5/GPT-4 for text processing
- **Poetry**: Dependency management
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
- Mock-based testing for Discord interactions
- Test files in tests/ directory mirror src/ structure

## Important Notes
- Bot requires FFmpeg installed for audio processing
- Poetry is the primary dependency manager (pyproject.toml)
- Supports deployment to Railway, AWS/GCP, Docker
- Audio files temporarily stored in data/ directory during processing
- Maximum audio file size: 25MB default
- Logging outputs to both console and bot.log file
