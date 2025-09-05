# ブランチ戦略とCI実行ルール (2025-08-31更新)

## 基本ブランチ戦略

### 個別Issueブランチ（基本戦略）
**命名規則**: `type/issue-number-description`

#### サポートされるブランチタイプ
- **feature/**: 新機能開発
  - 例: `feature/109-admin-dashboard`, `feature/110-api-v2`
- **fix/**: バグ修正
  - 例: `fix/111-auth-timeout`, `fix/112-memory-leak`
- **hotfix/**: 緊急修正
  - 例: `hotfix/113-security-patch`, `hotfix/114-critical-bug`
- **release/**: リリース準備
  - 例: `release/v1.2.0`, `release/v2.0.0-beta`
- **docs/**: ドキュメント更新
  - 例: `docs/115-api-documentation`, `docs/116-readme-update`

### Phase統合戦略（大規模機能用）
**命名規則**: `feature/phaseX`
- 複数の相互依存するIssueの統合
- 個別Issueブランチをphaseブランチにマージ
- Phase完了時にmainブランチに一括マージ

## CI/CD実行ルール

### Push時のCI実行対象
```yaml
push:
  branches:
    - main
    - develop
    - 'feature/**'   # 全featureブランチ
    - 'fix/**'       # 全fixブランチ
    - 'hotfix/**'    # 全hotfixブランチ
    - 'release/**'   # 全releaseブランチ
```

**実行内容**:
- ✅ 基本テスト（単体・統合）
- ✅ コード品質チェック（black, flake8, mypy）
- ✅ セキュリティチェック
- ❌ Docker統合テストはスキップ（リソース節約）

**目的**: 開発中の迅速なフィードバック提供

### Pull Request時のCI実行対象
```yaml
pull_request:
  branches:
    - main
    - develop
    - 'feature/phase*'  # Phase統合ブランチ
    - 'release/**'      # リリースブランチ
```

**実行内容**:
- ✅ 全テストスイート
- ✅ Docker統合テスト
- ✅ 包括的品質チェック
- ✅ セキュリティ検証

**目的**: マージ前の最終品質保証

## 実装された改善点（2025-08-31）

### 1. ワイルドカードパターン導入
- **従来**: 特定ブランチ名を手動追加
- **改善後**: パターンマッチングで自動対応

### 2. メンテナンスフリー化
- 新しいIssueブランチ作成時にCI設定変更不要
- ブランチ命名規則に従えば自動でCI実行

### 3. 包括的ブランチサポート
- feature, fix, hotfix, release, docsブランチに対応
- 各ブランチタイプに応じた適切なCI実行

## 開発者向けガイドライン

### 1. ブランチ作成手順
```bash
# 1. Issue番号を確認（例: Issue #120）
# 2. 適切なタイプとdescriptionでブランチ作成
git checkout -b feature/120-user-authentication main

# 3. 開発作業実行
# 4. Push時に自動でCI実行される
git push -u origin feature/120-user-authentication
```

### 2. PR作成時の注意事項
- **必須**: PR本文に `Closes #120` 記載
- **必須**: 全コミットに `(refs #120)` 含める
- CI全通過を確認してからマージ申請

### 3. CI実行タイミング理解
- **Push**: 開発フィードバック用（3-5分）
- **PR**: マージ前最終検証（5-10分）

## ブランチライフサイクル

### 個別Issueブランチ
```
1. Issue作成 → GitHub Projectに自動追加（Todo状態）
2. ブランチ作成（feature/issue-number-description）
3. 開発 → Push毎にCI実行
4. PR作成 → Issue状態がIn Progressに自動更新
5. レビュー・CI通過
6. マージ → Issue自動クローズ・Done状態・ブランチ削除
```

### Phase統合ブランチ
```
1. Phase計画作成
2. feature/phaseX ブランチ作成
3. 個別Issueブランチを順次マージ
4. Phase完了時にmainにPR作成
5. 包括的テスト・レビュー
6. mainにマージ・統合完了
```

## 自動化機能

### GitHub Actions連携
- **project-update.yml**: Project状態の自動更新
- **pr-validation.yml**: PR要件の自動チェック
- **ci.yml**: CI/CDパイプライン実行

### Issue・PR・Project連携
- Issue作成 → Project自動追加
- PR作成 → Issue状態自動更新
- PRマージ → Issue自動クローズ

## リソース効率化

### Push時の軽量化
- Docker統合テストをスキップ
- 基本的なテスト・品質チェックのみ
- 3-5分での迅速なフィードバック

### PR時の包括検証
- 全テストスイート実行
- Docker統合テスト含む
- マージ可否の最終判定

## 今後の拡張可能性

### 新しいブランチタイプ追加
```yaml
# 必要に応じて追加可能
- 'chore/**'     # メンテナンス作業
- 'perf/**'      # パフォーマンス改善
- 'refactor/**'  # リファクタリング
```

### 条件分岐の詳細化
```yaml
# 特定条件での除外も可能
branches-ignore:
  - '**-wip'     # WIPブランチは除外
  - '**-temp'    # 一時ブランチは除外
```

このルールにより、Issue #109以降の全ブランチが自動的にCI対象となり、開発効率と品質保証のバランスが最適化されています。
