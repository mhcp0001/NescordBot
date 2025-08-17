# タスクリスト - NescordBot 開発・運用基盤整備

## 概要

- 総タスク数: 48
- 推定作業時間: 8週間（各Phase 2週間）
- 優先度: 高（基盤構築）
- **ブランチ戦略**: GitHub Flow（機能別ブランチ → mainへのPR）

## ブランチ命名規則

- `feature/機能名` - 新機能開発
- `refactor/改善名` - リファクタリング・構造改善
- `docs/文書名` - ドキュメント更新
- `test/テスト名` - テスト追加・改善
- `ci/設定名` - CI/CD設定変更
- `hotfix/修正名` - 緊急バグ修正

## タスク一覧

### Phase 1: MVP基盤 + 最初の機能（2週間）

#### Task 1.1: プロジェクト初期設定
- [x] プロジェクト構造の作成（src/, tests/, docs/）
- [x] .env.exampleファイルの作成
- [x] .gitignoreの更新（.env, *.log, __pycache__/）
- [x] README.mdの基本手順作成
- **完了条件**: プロジェクト構造が整い、環境変数サンプルが用意される
- **依存**: なし
- **推定時間**: 1時間

#### Task 1.2: Poetry環境構築
- [x] pyproject.tomlの作成（Python 3.11+指定）
- [x] 基本依存関係の追加（discord.py, python-dotenv, pydantic）
- [x] 開発依存関係の追加（pytest, black, flake8, mypy）
- [x] poetry.lockの生成
- **完了条件**: Poetry環境で依存関係がインストール可能
- **依存**: Task 1.1
- **推定時間**: 1時間

#### Task 1.3: ConfigManagerの実装
- [x] src/config.pyの作成
- [x] Pydanticを使用したBotConfig modelの定義
- [x] .envからの環境変数読み込み
- [x] バリデーション処理の実装
- **完了条件**: 環境変数が正しく読み込まれ、型検証される
- **依存**: Task 1.2
- **推定時間**: 2時間

#### Task 1.4: LoggerServiceの実装
- [x] src/logger.pyの作成
- [x] 標準loggingの設定（コンソール + ファイル出力）
- [x] ログレベルの環境変数制御
- [x] フォーマッタの設定
- **完了条件**: 構造化されたログが出力される
- **依存**: Task 1.3
- **推定時間**: 1時間

#### Task 1.5: BotCoreの基本実装
- [x] src/bot.pyの作成
- [x] NescordBotクラスの実装（commands.Bot継承）
- [x] setup_hookメソッドの実装
- [x] on_readyイベントハンドラ
- [x] グローバルエラーハンドラ（on_error, on_command_error）
- **完了条件**: Botが起動し、基本的なイベントを処理できる
- **依存**: Task 1.3, Task 1.4
- **推定時間**: 3時間

#### Task 1.6: GeneralCogの実装
- [x] src/cogs/general.pyの作成
- [x] pingコマンドの実装
- [x] helpコマンドのカスタマイズ
- [x] statusコマンドの実装（Bot情報表示）
- **完了条件**: 基本コマンドが動作する
- **依存**: Task 1.5
- **推定時間**: 2時間

#### Task 1.7: 起動スクリプトの作成
- [x] run.pyまたはmain.pyの作成
- [x] ServiceContainerの基本実装
- [x] 非同期メイン関数の実装
- [x] グレースフルシャットダウンの実装
- **完了条件**: poetry run python run.pyでBot起動
- **依存**: Task 1.5, Task 1.6
- **推定時間**: 2時間

#### Task 1.8: 基本的なテストの作成
- [x] tests/conftest.pyの作成（pytest fixtures）
- [x] tests/test_config.pyの作成
- [x] tests/test_general_cog.pyの作成
- [x] モックコンテキストの実装
- **完了条件**: 基本的なユニットテストがパスする
- **依存**: Task 1.6
- **推定時間**: 3時間

#### Task 1.9: GitHub Actions CI設定
- [x] .github/workflows/ci.ymlの作成
- [x] Pythonセットアップ
- [x] Poetry依存関係インストール
- [x] pytest実行
- [x] コード品質チェック（black, flake8）
- **完了条件**: PRでCIが自動実行される
- **依存**: Task 1.8
- **推定時間**: 2時間

#### Task 1.10: Railway手動デプロイ準備
- [x] requirements.txt生成（poetry export）
- [x] Procfileの作成
- [x] runtime.txtの作成（Python 3.11）
- [x] Railway設定ドキュメント作成
- **完了条件**: Railwayにデプロイ可能な状態
- **依存**: Task 1.7
- **推定時間**: 2時間

### Phase 2: 開発基盤強化 + 機能追加（2週間）

#### Task 2.1: DatabaseService設計
- [x] src/services/__init__.pyの作成
- [x] IDataStore抽象基底クラスの定義
- [x] SqliteDataStoreクラスの設計
- [x] エラーハンドリング設計
- **完了条件**: データストア抽象化レイヤーが定義される
- **依存**: Phase 1完了
- **推定時間**: 2時間
- **ブランチ**: `feature/database-service-design`

#### Task 2.2: aiosqlite実装
- [x] aiosqlite依存関係追加
- [x] SqliteDataStoreの実装
- [x] Key-Value操作メソッド（get, set, delete）
- [x] JSON操作メソッド（get_json, set_json）
- [x] 接続プール管理
- **完了条件**: 非同期でデータ永続化が可能
- **依存**: Task 2.1
- **推定時間**: 3時間
- **ブランチ**: `feature/database-service-impl`

#### Task 2.3: データベースマイグレーション
- [x] migrations/ディレクトリ構造作成
- [x] 初期スキーマSQL作成
- [x] マイグレーション実行スクリプト
- [x] バージョン管理システム
- **完了条件**: データベース構造の変更が管理される
- **依存**: Task 2.2
- **推定時間**: 2時間
- **ブランチ**: `feature/database-migrations`

#### Task 2.4: ServiceContainerの拡張
- [x] DatabaseServiceの統合
- [x] 起動時の初期化処理
- [x] シャットダウン時のクリーンアップ
- [x] 依存性注入の実装
- **完了条件**: 全サービスが適切に管理される
- **依存**: Task 2.2
- **推定時間**: 2時間
- **ブランチ**: `feature/service-container`

#### Task 2.5: テスト基盤の強化
- [x] pytest-asyncioの設定最適化
- [x] pytest-mockの統合
- [x] pytest-covの設定（カバレッジ60%目標）
- [x] テスト用DBフィクスチャ
- **完了条件**: 非同期テストが安定して実行される
- **依存**: Task 2.4
- **推定時間**: 3時間
- **ブランチ**: `test/async-framework`

#### Task 2.6: コード品質ツール統合
- [x] blackの設定（pyproject.toml）
- [x] flake8の設定（.flake8）
- [x] isortの設定
- [x] mypyの設定（mypy.ini）
- [x] pre-commitフックの設定
- **完了条件**: コード品質が自動チェックされる
- **依存**: なし
- **推定時間**: 2時間
- **ブランチ**: `ci/code-quality`

#### Task 2.7: ログ閲覧コマンドの実装
- [x] src/cogs/admin.pyの作成
- [x] logsコマンドの実装（最新ログ表示）
- [x] ログレベルフィルタリング
- [x] ページネーション機能
- **完了条件**: Discord上でログが確認できる
- **依存**: Task 2.4
- **推定時間**: 3時間
- **ブランチ**: `feature/admin-log-commands`

#### Task 2.8: 設定管理コマンドの実装
- [x] configコマンドの実装（設定表示）
- [x] setconfigコマンドの実装（設定変更）
- [x] 設定永続化（DatabaseService使用）
- [x] 権限チェック機能
- **完了条件**: Discord上で設定が管理できる
- **依存**: Task 2.7
- **推定時間**: 3時間
- **ブランチ**: `feature/admin-config-commands`

#### Task 2.9: DatabaseServiceのテスト
- [x] tests/test_database_service.pyの作成
- [x] 基本操作のテスト
- [x] エラーケースのテスト
- [x] 同時実行テスト
- **完了条件**: DatabaseServiceのカバレッジ80%以上
- **依存**: Task 2.5
- **推定時間**: 2時間
- **ブランチ**: `test/database-service`

#### Task 2.10: 統合テストの追加
- [x] tests/integration/test_bot_lifecycle.pyの作成
- [x] Bot起動・終了テスト
- [x] コマンド実行テスト
- [x] エラーハンドリングテスト
- **完了条件**: End-to-Endテストがパスする
- **依存**: Task 2.9
- **推定時間**: 3時間
- **ブランチ**: `test/integration-suite`

### Phase 3: GitHub連携機能 + CD導入（2週間）

#### Task 3.1: GitHubService設計
- [ ] src/services/github.pyの作成
- [ ] IGitHubService抽象基底クラス
- [ ] データモデル定義（PR, Branch, Commit）
- [ ] カスタム例外クラス定義
- **完了条件**: GitHub API操作の抽象化層が定義される
- **依存**: Phase 2完了
- **推定時間**: 2時間
- **ブランチ**: `feature/github-service-design`

#### Task 3.2: aiohttp実装
- [ ] aiohttp, aiocache依存関係追加
- [ ] HTTPクライアントセッション管理
- [ ] 基本的なAPI呼び出しメソッド
- [ ] エラーハンドリング
- **完了条件**: 非同期でGitHub APIを呼び出せる
- **依存**: Task 3.1
- **推定時間**: 3時間
- **ブランチ**: `feature/github-http-client`

#### Task 3.3: レート制限管理
- [ ] レート制限チェック機能
- [ ] 429エラーのリトライ処理
- [ ] 指数バックオフ実装
- [ ] レート制限状態の監視
- **完了条件**: APIレート制限を超えない
- **依存**: Task 3.2
- **推定時間**: 3時間
- **ブランチ**: `feature/github-rate-limiting`

#### Task 3.4: キャッシュ戦略実装
- [ ] ETagベースのキャッシュ
- [ ] 条件付きリクエスト（304処理）
- [ ] TTLベースのメモリキャッシュ
- [ ] キャッシュ無効化処理
- **完了条件**: API呼び出しが最小化される
- **依存**: Task 3.3
- **推定時間**: 3時間
- **ブランチ**: `feature/github-caching`

#### Task 3.5: PR作成機能の実装
- [ ] create_prメソッドの実装
- [ ] create_branchメソッドの実装
- [ ] commit_filesメソッドの実装
- [ ] ファイルツリー操作
- **完了条件**: プログラムからPRが作成できる
- **依存**: Task 3.4
- **推定時間**: 4時間
- **ブランチ**: `feature/github-pr-creation`

#### Task 3.6: GitHubCogの実装
- [ ] src/cogs/github.pyの作成
- [ ] pr_createコマンド
- [ ] repo_infoコマンド
- [ ] エラーメッセージのユーザーフレンドリー化
- **完了条件**: Discord経由でGitHub操作が可能
- **依存**: Task 3.5
- **推定時間**: 3時間
- **ブランチ**: `feature/github-discord-commands`

#### Task 3.7: Obsidian連携機能
- [ ] Obsidian Vault構造の定義
- [ ] Fleeting noteテンプレート作成
- [ ] フロントマター生成処理
- [ ] ファイル命名規則実装
- **完了条件**: Obsidian形式のMarkdownが生成される
- **依存**: Task 3.6
- **推定時間**: 3時間
- **ブランチ**: `feature/obsidian-integration`

#### Task 3.8: Railway CD設定
- [ ] .github/workflows/deploy.ymlの作成
- [ ] Railway CLI設定
- [ ] 環境変数管理
- [ ] デプロイメントトリガー設定
- **完了条件**: mainブランチプッシュで自動デプロイ
- **依存**: なし
- **推定時間**: 2時間
- **ブランチ**: `ci/railway-deployment`

#### Task 3.9: GitHubServiceのテスト
- [ ] tests/test_github_service.pyの作成
- [ ] モックGitHub APIレスポンス
- [ ] レート制限テスト
- [ ] キャッシュテスト
- **完了条件**: GitHubServiceカバレッジ80%以上
- **依存**: Task 3.5
- **推定時間**: 3時間
- **ブランチ**: `test/github-service`

#### Task 3.10: 統合テスト（GitHub機能）
- [ ] End-to-End PR作成テスト
- [ ] エラーリカバリーテスト
- [ ] 並行実行テスト
- [ ] 実際のテストリポジトリでの検証
- **完了条件**: GitHub連携が安定動作する
- **依存**: Task 3.9
- **推定時間**: 3時間
- **ブランチ**: `test/github-integration`

### Phase 4: 運用基盤完成 + 本格運用（2週間）

#### Task 4.1: VoiceCog設計
- [ ] src/cogs/voice.pyの構造設計
- [ ] OpenAI API統合設計
- [ ] 音声ファイル処理フロー設計
- [ ] エラーハンドリング設計
- **完了条件**: 音声処理アーキテクチャが定義される
- **依存**: Phase 3完了
- **推定時間**: 2時間

#### Task 4.2: OpenAI API統合
- [ ] openai依存関係追加
- [ ] Whisper API呼び出し実装
- [ ] GPT API呼び出し実装
- [ ] レート制限とエラー処理
- **完了条件**: OpenAI APIが利用可能
- **依存**: Task 4.1
- **推定時間**: 3時間

#### Task 4.3: 音声メッセージ処理
- [ ] 音声ファイルダウンロード処理
- [ ] 一時ファイル管理
- [ ] Whisper文字起こし実装
- [ ] GPT整形処理実装
- **完了条件**: 音声が文字起こしされる
- **依存**: Task 4.2
- **推定時間**: 4時間
- **ブランチ**: `feature/voice-transcription`

#### Task 4.4: ヘルスチェック実装
- [ ] /healthエンドポイント設計
- [ ] 簡易HTTPサーバー実装
- [ ] システム状態チェック
- [ ] Railway統合
- **完了条件**: 外部監視が可能
- **依存**: なし
- **推定時間**: 2時間
- **ブランチ**: `feature/health-monitoring`

#### Task 4.5: メトリクス収集
- [ ] 実行時間記録
- [ ] エラー率計測
- [ ] メモリ使用量監視
- [ ] ログへの出力
- **完了条件**: パフォーマンスが可視化される
- **依存**: Task 4.4
- **推定時間**: 3時間
- **ブランチ**: `feature/performance-metrics`

#### Task 4.6: ドキュメント整備
- [ ] APIドキュメント生成
- [ ] デプロイメントガイド作成
- [ ] トラブルシューティングガイド
- [ ] コントリビューションガイド
- **完了条件**: 開発者向けドキュメント完備
- **依存**: なし
- **推定時間**: 4時間
- **ブランチ**: `docs/documentation-complete`

#### Task 4.7: パフォーマンス最適化
- [ ] 非同期処理の最適化
- [ ] メモリリーク調査
- [ ] キャッシュ戦略の調整
- [ ] データベースインデックス最適化
- **完了条件**: 応答時間が目標値以内
- **依存**: Task 4.5
- **推定時間**: 3時間
- **ブランチ**: `refactor/performance-optimization`

#### Task 4.8: セキュリティ強化
- [ ] 入力検証の強化
- [ ] ログマスキング実装
- [ ] 権限管理の徹底
- [ ] セキュリティ監査
- **完了条件**: セキュリティ脆弱性がない
- **依存**: なし
- **推定時間**: 3時間
- **ブランチ**: `refactor/security-hardening`

#### Task 4.9: 本番環境テスト
- [ ] 負荷テスト実施
- [ ] 障害復旧テスト
- [ ] バックアップ・リストアテスト
- [ ] モニタリング動作確認
- **完了条件**: 本番運用の準備完了
- **依存**: Task 4.7, Task 4.8
- **推定時間**: 3時間
- **ブランチ**: `test/production-readiness`

#### Task 4.10: リリース準備
- [ ] バージョンタグ付け
- [ ] リリースノート作成
- [ ] デプロイメントチェックリスト
- [ ] 運用手順書の最終確認
- **完了条件**: v1.0.0リリース可能
- **依存**: Task 4.9
- **推定時間**: 2時間
- **ブランチ**: `release/v1.0.0`

## 実装順序

1. Phase 1から順次実行（基盤なしに機能追加は不可能）
2. 各Phase内では依存関係に従って実装
3. テストは各機能実装直後に作成
4. CI/CDは早期に構築して継続的に活用

## リスクと対策

- **データ永続性問題（Railway/Heroku）**: Phase 2でRedis対応を検討
- **GitHub APIレート制限**: キャッシュとETag活用で最小化
- **非同期リソース管理**: ServiceContainerパターンで一元管理
- **テストの複雑化**: モックとフィクスチャで簡潔に保つ

## ブランチ戦略 - GitHub Flow実装ガイド

### 基本原則
- **1タスク = 1ブランチ = 1PR** - 各タスクは独立したブランチで実装
- **mainブランチは常にデプロイ可能** - mainにマージされるコードは完全にテスト済み
- **短期間のブランチ** - 機能ブランチは2-3日以内に完了してマージ

### ワークフロー手順

#### 1. 新機能開始時
```bash
# mainから最新版を取得
git checkout main
git pull origin main

# 新しい機能ブランチを作成（タスクリストのブランチ名を使用）
git checkout -b feature/database-service-impl
```

#### 2. 開発 & コミット
```bash
# 実装作業
# ... Claude Codeと協働で実装 ...

# 変更をステージング
git add src/services/database.py tests/test_database_service.py

# conventional commits形式でコミット
git commit -m "feat(database): implement async SQLite data store with aiosqlite

- Add IDataStore interface for database abstraction
- Implement DatabaseService with async operations
- Add comprehensive test suite with 95% coverage
- Support key-value and JSON operations

Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

#### 3. プッシュ & PR作成
```bash
# リモートにプッシュ
git push origin feature/database-service-impl

# GitHub UI または gh CLI でPR作成
gh pr create --title "feat(database): implement DatabaseService with async SQLite" \
             --body "## 概要
Task 2.2の実装: aiosqliteを使用したDatabaseServiceの実装

## 完了条件
- [x] 非同期でデータ永続化が可能
- [x] Key-Value操作メソッド実装
- [x] JSON操作メソッド実装
- [x] 接続プール管理
- [x] 包括的なテストスイート

## テスト結果
- Unit tests: 11/11 passing
- Coverage: 95%
- All pre-commit hooks passing

Generated with [Claude Code](https://claude.ai/code)"
```

#### 4. レビュー & マージ
- GitHub ActionsでCI実行を確認
- コードレビュー実施（セルフレビューまたはペアレビュー）
- CIが成功したらmainにマージ
- ブランチ削除

### 並行開発の管理

#### 依存関係がある場合
```bash
# Task 2.2完了後、Task 2.4を開始
git checkout main
git pull origin main  # Task 2.2のマージ内容を取得
git checkout -b feature/service-container
```

#### 依存関係がない場合
```bash
# Task 2.6（コード品質）は並行して進行可能
git checkout main
git checkout -b ci/code-quality
```

## 注意事項

- **各タスクは1つのPRで完結させる** - ブランチ名はタスクリストのブランチ名を使用
- **コミットメッセージは conventional commits 形式** - feat:, fix:, docs:, test:, refactor:, ci:等
- **テストが通らないコードはマージしない** - pre-commitフック + CI通過が必須
- **不明点は実装前にIssueで議論する** - 設計判断は記録を残して決定
- **mainとの乖離を最小限に** - 長期ブランチは避け、こまめにリベースまたはマージ

## 実装開始ガイド

1. このタスクリストに従って順次実装を進めてください
2. 各タスクの開始時にTodoWriteでin_progressに更新
3. 完了時はcompletedに更新
4. 問題発生時は速やかに報告してください
5. 1日の作業開始時に進捗を確認し、計画を調整してください
