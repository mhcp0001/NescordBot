---
description: GitHub CLI を使用して、提供された内容から Pull Request を作成します。
allowed-tools: [Bash, Read, Edit, TodoWrite]
---

# PRを作成

- Read @.github/PULL_REQUEST_TEMPLATE.md に従うこと
- Draftで作成すること
- push時は`git push -u origin <branch_name>` のように `--set-upstream` を指定すること
- コマンドの例: `gh pr create --draft --title "title" --body "body"`
