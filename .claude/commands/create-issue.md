---
description: GitHub CLI を使用して、提供された内容から Issue を作成します。
allowed-tools: [Bash, Read, Edit, TodoWrite]
---
# GitHub Issue 作成コマンド
## 要件(MUST)

- **言語**: Issue の内容は英語で記載
- テンプレートは .github/ISSUE_TEMPLATE/xxxx.md を使用
- **プロジェクト**: 作成後、Project ID xx に追加 PROJECT_ID="PVT_projectxxxxxxx"
- **アサイン**: アサインは行わない
- **ラベル付け**:
   - フロントエンド実装の場合: `FE` ラベルを追加
   - バックエンド実装の場合: `BE` ラベルを追加
   - インフラ実装の場合: `Infra` ラベルを追加
- `--parent=${issue_id}` フラグが指定された場合は、親 Issue の NodeID を設定
- `--next` flag が指定された場合は、プロジェクトのフィールドで sprint = @next を設定。sprintのデフォルトはnext
- `--current` flag が指定された場合は、プロジェクトのフィールドで sprint = @current を設定
- `--feature` flag が指定された場合は、プロジェクトのフィールドで Issue type = Feature を設定
- `--epic` flag が指定された場合は、プロジェクトのフィールドで Issue Type = Epic を設定
- `--task` flag が指定された場合は、プロジェクトのフィールドで Issue Type = Task を設定。Issue Typeのデフォルトは Task
- `--backlog` flag が指定された場合は、プロジェクトのフィールドで status = backlog
   を設定。
- `--ready` flag が指定された場合は、プロジェクトのフィールドで status = ready を設定。statusのデフォルトはready。

## 設定

## GitHub ID体系の理解

GitHub APIには複数のID体系があり、適切な使い分けが重要です：

### ID体系の種類

| 種類 | 形式 | 例 | 用途 |
|------|------|-----|------|
| Issue番号 | 数値 | `36635` | URL、人間が読む識別子 |
| Issue Node ID (GraphQL) | `I_kwDO...` | `I_kwDOxxxxxxx` | GraphQL API専用 |
| Project ID (GraphQL) | `PVT_kwDO...` | `PVT_projectxxxxxxx` | Project V2 API専用 |
| Project Item ID (GraphQL) | `PVTI_lADO...` | `PVTI_xxxxxxxxxxxxxxxx` | Project内のIssue実体 |

### Project Item IDの確実な取得方法

**⚠️ 重要**: `gh project item-list`は新規作成直後のIssueを見つけられない場合があります。
以下の方法が確実です：

```bash
# 1. Issue番号からIssue Node IDを取得
ISSUE_NODE_ID=$(gh issue view 36635 --json id --jq '.id')

# 2. Issue Node IDからProject Item IDを取得
PROJECT_ITEM_ID=$(gh api graphql -f query="
query {
  node(id: \"$ISSUE_NODE_ID\") {
    ... on Issue {
      projectItems(first: 10) {
        nodes {
          id
          project {
            number
          }
        }
      }
    }
  }
}" | jq -r '.data.node.projectItems.nodes[] | select(.project.number == 1) | .id')

echo "Project Item ID: $PROJECT_ITEM_ID"
```

### プロジェクトの設定の取得

以下のコマンドで、プロジェクトのSprint,Status,IssueTypeの設定を取得できます。

```bash
gh api graphql -f query='
  query {
    organization(login: "primenumber-dev") {
      projectV2(number: 1) {
        fields(first: 20) {
          nodes {
            __typename
            ... on ProjectV2Field {
              id
              name
            }
            ... on ProjectV2SingleSelectField {
              id
              name
              options {
                id
                name
              }
            }
            ... on ProjectV2IterationField {
              id
              name
              configuration {
                iterations {
                  id
                  title
                  startDate
                }
              }
            }
          }
        }
      }
    }
  }' | jq '.data.organization.projectV2.fields.nodes[] | select(.name == "Sprint" or .name == "Status" or .name == "Issue Type")'
```


### Sprintの設定

Iteration で管理されています。
以下のコマンドで、次のSprintのIteration IDを取得できます。
スプリントは１週間で区切っています。日付からnext sprint, current sprintを判別して、IDを取得してください。

- Sprint NodeID: PVTIF_xxxxxxxxxxxxxxxx

```bash
  gh project item-edit \
    --id <item-id> \
    --field-id PVTIF_xxxxxxxxxxxxxxxx \
    --project-id PVT_projectxxxxxxx \
    --iteration-id <next-sprint-iteration-id>
```


```bash
gh api graphql -f query='
mutation {
  updateProjectV2ItemFieldValue(
    input: {
      projectId: "PVT_projectxxxxxxx"
      itemId: "PVTI_xxxxxxxxxxxxxxxx"
      fieldId: "PVTSSF_xxxxxxxxxxxxxxxx"
      value: { singleSelectOptionId: "xxxxxxxx" }
    }
  ) {
    projectV2Item {
      id
    }
  }
}' --jq '.data.updateProjectV2ItemFieldValue.projectV2Item.id'
```

### IssueType の設定

- issueType NodeID: PVTSSF_xxxxxxxxxxxxxxxx
  - issueType option
    - Feature: aaaaaaaa
    - Task: bbbbbbbb
    - Epic: cccccccc

- status NodeID: PVTSSF_yyyyyyyyyyyyyyyy
  - option
    - Backlog: dddddddd
    - Ready: eeeeeeee
    - Todo: ffffffff

## 実行手順

### 前提手順: 親Issueの分析（親Issueが指定された場合）

親Issue (`--parent=${issue_id}`) が指定された場合は、Issue作成前に以下の手順を実行する：

1. **親Issueの詳細確認**:
```bash
gh issue view ${PARENT_ISSUE_ID}
```

2. **親Issueのコメント全体確認**:
```bash
gh issue view ${PARENT_ISSUE_ID} --comments
```

3. **内容分析とまとめ**:
   - 親Issueの目的・要件を理解
   - 既存のコメントから追加の文脈・制約を把握
   - 関連するタスクや依存関係を特定
   - 親Issueの全体的な進捗状況を確認

4. **分析結果を基にした子Issueの内容調整**:
   - 親Issueとの関連性を明確に記述
   - 親Issueで議論された内容を反映
   - 適切なスコープと優先度を設定

### Issue template の確認

.github/ISSUE_TEMPLATE/xxxx.md を確認し、Issueの構成を確認します。

### メイン手順

1. Issue を作成:
```bash
gh issue create \
  --title "Issue Title" \
  --body "Issue description..." \
  --label "FE"
```

Task にはAI Coding Agent のタスクを

2. Project に追加:
```bash
gh project item-add 1 --owner primenumber-dev --url ${ISSUE_URL}
```

3. 親Issue設定:

`--parent=${issue_id}` フラグで指定された場合のみ親子関係を設定する。

```bash
# --parent フラグで指定されたIssueを親Issueに設定する場合

# 1. 親IssueのNodeIDを取得
PARENT_NODE_ID=$(gh issue view ${PARENT_ISSUE_ID} --json id --jq '.id')

# 2. 作成したIssueのNodeIDを取得
CHILD_NODE_ID=$(gh issue view ${ISSUE_NUMBER} --json id --jq '.id')

# 3. 親子関係を設定
gh api graphql -f query="
mutation {
  addSubIssue(input: {
    issueId: \"${PARENT_NODE_ID}\"
    subIssueId: \"${CHILD_NODE_ID}\"
  }) {
    issue { title }
    subIssue { title }
  }
}"
```

4. ProjectでTypeを設定:

Issue IDを取得
PROJECT_ID="PVT_projectxxxxxxx"  # Project 1のID
ISSUE IDを取得するために、以下のコマンドを使用します。


### 効率的なワンライン実行パターン

```bash
# 1. Issue作成とProject追加を並列実行
gh issue create \
  --title "[COMETA] Issue Title" \
  --body "Issue description..." \
  --label "BE" && \
gh project item-add ${project_id} --owner primenumber-dev --url https://github.com/primenumber-dev/repo_xxxxx/issues/$(gh issue list --limit 1 --json number --jq '.[0].number')

# 2. 親子関係設定（親Issue指定時のみ）
PARENT_NODE_ID=$(gh issue view ${PARENT_ISSUE_ID} --json id --jq '.id')
CHILD_NODE_ID=$(gh issue view ${ISSUE_NUMBER} --json id --jq '.id')

gh api graphql -f query="
mutation {
  addSubIssue(input: {
    issueId: \"${PARENT_NODE_ID}\"
    subIssueId: \"${CHILD_NODE_ID}\"
  }) {
    issue { title }
    subIssue { title }
  }
}"

# 3. プロジェクトフィールド設定（並列実行で効率化）
ISSUE_NODE_ID=$(gh issue view ${ISSUE_NUMBER} --json id --jq '.id')
PROJECT_ITEM_ID=$(gh api graphql -f query="
query {
  node(id: \"$ISSUE_NODE_ID\") {
    ... on Issue {
      projectItems(first: 10) {
        nodes {
          id
          project { number }
        }
      }
    }
  }
}" | jq -r '.data.node.projectItems.nodes[] | select(.project.number == 1) | .id')

echo "Project Item ID: $PROJECT_ITEM_ID"

PROJECT_ID="PVT_projectxxxxxxx"

# 全フィールドを並列設定（効率化）
gh project item-edit --id ${PROJECT_ITEM_ID} --field-id PVTSSF_xxxxxxxxxxxxxxxx --project-id ${PROJECT_ID} --single-select-option-id bbbbbbbb &
gh project item-edit --id ${PROJECT_ITEM_ID} --field-id PVTSSF_yyyyyyyyyyyyyyyy --project-id ${PROJECT_ID} --single-select-option-id dddddddd &
gh project item-edit --id ${PROJECT_ITEM_ID} --field-id PVTIF_xxxxxxxxxxxxxxxx --project-id ${PROJECT_ID} --iteration-id gggggggg &

# 全ての並列プロセスの完了を待つ
wait

# 最終ステップ: 設定内容とIssue情報の出力
echo "=== Issue作成完了 ==="
echo "Issue URL: https://github.com/primenumber-dev/repo_xxxxx/issues/${ISSUE_NUMBER}"
echo "Sprint: Next"
echo "Issue Type: Task"
echo "Status: Ready"
```


## 重要な注意事項

### API選択の原則
- **Project V2操作**: 必ずGraphQL APIとNode ID形式を使用
- **REST APIのProject Item ID**: `gh project item-list`の結果は使用不可
- **確実な方法**: Issue Node ID → Project Item ID の順で取得

### トラブルシューティング
- **Project Item IDが見つからない場合**: 新規Issue作成直後は索引化に時間がかかる
- **間違ったProject ID使用**: `PVT_projectxxxxxxx`が正しいID
- **GraphQL vs REST**: Project操作にはGraphQL Node IDが必須

### 実行時の確認事項
- Issue作成後、Project追加まで少し待機
- Project Item IDは毎回動的に取得
- 親Issue設定はIssue Node ID使用

### 最終ステップ: 設定内容の出力

全ての設定完了後、以下の情報を出力する：

```bash
echo "=== Issue作成完了 ==="
echo "Issue URL: https://github.com/primenumber-dev/repo_xxxxx/issues/${ISSUE_NUMBER}"
echo "Sprint: ${SPRINT_NAME}"
echo "Issue Type: ${ISSUE_TYPE}"
echo "Status: ${STATUS}"
```
