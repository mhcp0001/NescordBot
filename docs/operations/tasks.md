# タスクリスト - NescordBot 開発・運用基盤整備

## 概要

- **Phase 1-3**: 48タスク (8週間) - 基盤構築・機能実装・運用基盤
- **Phase 4**: 32タスク (12週間) - PKM機能「自分の第二の脳を育てるBot」
- **Phase 5**: 10タスク (2週間) - 運用基盤完成・本格運用
- 総タスク数: 90タスク
- 推定作業時間: 22週間
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
- [x] Obsidian Vault構造の定義
- [x] Fleeting noteテンプレート作成
- [x] フロントマター生成処理
- [x] ファイル命名規則実装
- **完了条件**: Obsidian形式のMarkdownが生成される
- **依存**: Task 3.6
- **推定時間**: 3時間
- **ブランチ**: `feature/obsidian-integration`
- **状態**: ✅ 完了（2025-08-17）

##### Task 3.7.1: Obsidian GitHub統合 - 基盤構築 ✅ 完了
- [x] **依存関係追加**
  - [x] PyGithub 2.1+ の追加
  - [x] GitPython 3.1+ の追加
  - [x] pathvalidate の追加（ファイル名検証用）
- [x] **セキュリティコンポーネント**
  - [x] SecurityValidator クラス実装
  - [x] XSS・インジェクション攻撃検出
  - [x] ファイル名・パス検証機能
- [x] **設定管理拡張**
  - [x] BotConfig クラスの拡張（複数インスタンス対応）
  - [x] 環境変数設定の追加
  - [x] 設定バリデーション機能の実装
- **完了条件**: GitHub統合の基盤となるライブラリとセキュリティ機能が整う
- **依存**: Task 3.7
- **推定時間**: 4時間（2日）
- **ブランチ**: `feature/obsidian-github-base`
- **状態**: ✅ 完了（2025-08-19, Issue #48, PR #55）

##### Task 3.7.2: Obsidian GitHub統合 - Git操作層 ✅ 完了
- [x] **GitOperationManager実装**
  - [x] ローカルリポジトリ管理
  - [x] 安全なGit操作（パストラバーサル防止）
  - [x] コミット・プッシュ機能
- [x] **競合回避機能**
  - [x] インスタンス分離方式
  - [x] ファイルロック機構
  - [x] 並行実行制御
- [x] **エラーハンドリング**
  - [x] Git操作失敗時の処理
  - [x] ネットワーク障害対応
  - [x] ローカルキャッシュフォールバック
- **完了条件**: 安全なGit操作が可能になる
- **依存**: Task 3.7.1
- **推定時間**: 4時間（2日）
- **ブランチ**: `feature/obsidian-git-operations`
- **状態**: ✅ 完了（2025-08-19, Issue #49, PR #55）

##### Task 3.7.3: Obsidian GitHub統合 - キュー永続化 🔥 高優先度
- [ ] **SQLiteキューテーブル設計**
  - [ ] obsidian_file_queue テーブル作成
  - [ ] obsidian_dead_letter_queue テーブル作成
  - [ ] インデックス最適化
- [ ] **PersistentQueue実装**
  - [ ] キューCRUD操作
  - [ ] Bot再起動時の復旧機能
  - [ ] 失敗タスクのDLQ移動
- [ ] **キュー復旧機能**
  - [ ] processing状態タスクの検出
  - [ ] pending状態への復旧ロジック
  - [ ] メモリキューへの復元
- **完了条件**: Bot再起動後もタスクが継続処理される
- **依存**: Task 3.7.2
- **推定時間**: 2時間（1日）
- **ブランチ**: `feature/obsidian-queue-sqlite`

##### Task 3.7.4: Obsidian GitHub統合 - 認証とバッチ処理 🔥 高優先度
- [ ] **GitHubAuthManager実装**
  - [ ] PAT認証実装
  - [ ] GitHub App認証実装（将来対応）
  - [ ] 認証方式の動的切り替え
- [ ] **BatchProcessor更新**
  - [ ] SQLite永続化統合
  - [ ] キューID管理
  - [ ] バッチ処理最適化
- [ ] **エラーハンドリング強化**
  - [ ] 指数バックオフリトライ
  - [ ] サーキットブレーカーパターン
  - [ ] GitHub APIエラー処理
- **完了条件**: GitHub APIを使用したバッチ処理が安定動作する
- **依存**: Task 3.7.3
- **推定時間**: 4時間（2日）
- **ブランチ**: `feature/obsidian-github-auth`

##### Task 3.7.5: Obsidian GitHub統合 - 統合テスト 🔥 高優先度
- [ ] **ObsidianGitHubService統合**
  - [ ] 全コンポーネント統合
  - [ ] 既存ObsidianServiceとの置き換え
  - [ ] 設定による動作切り替え実装
- [ ] **包括的テスト実装**
  - [ ] SecurityValidator テスト
  - [ ] GitOperationManager テスト
  - [ ] PersistentQueue テスト
  - [ ] BatchProcessor テスト
- [ ] **エンドツーエンドテスト**
  - [ ] Discord→GitHub→Obsidian vault 全体フロー
  - [ ] エラー時のフォールバック確認
  - [ ] 既存機能との互換性確認
- **完了条件**: GitHub統合が完全に動作し、テストカバレッジ80%達成
- **依存**: Task 3.7.4
- **推定時間**: 2時間（1日）
- **ブランチ**: `test/obsidian-github-integration`

#### Task 3.8: テキストメッセージ処理機能 - Fleeting Note拡張 🔥 高優先度
- **Issue**: #72 - テキストメッセージ処理機能メインタスク
- **Project**: Nescord Project (登録済み)
- **設計書**: docs/design/text_message_fleeting_note.md
- **🔄 Gemini改善案採用**: 3フェーズ・8タスク分割によるリスク軽減アプローチ

##### 🔐 フェーズ1: 基盤リファクタリングと安定化（既存機能保護重視）

**Task 3.8.1: NoteProcessingService作成**
- [ ] src/services/note_processing.py作成
- [ ] 既存process_with_aiメソッドをVoice cogから抽出
- [ ] 音声・テキスト共通のAI処理サービスとして汎用化
- [ ] 入力形式（音声/テキスト）を知らない独立したモジュール設計
- **完了条件**: 汎用的なテキスト処理サービスが作成される
- **依存**: Task 3.7.5完了
- **推定時間**: 3時間（1日）
- **ブランチ**: `refactor/note-processing-service`
- **Issue**: #73 (Projectに登録済み)

**Task 3.8.2: Voice Cogリファクタリング**
- [ ] 既存Voice cogを新しいNoteProcessingServiceを使用するよう修正
- [ ] 音声処理フローの動作確認・互換性保証
- [ ] 既存APIインターフェースの維持
- **完了条件**: 既存Voice機能が新サービス経由で動作
- **依存**: Task 3.8.1
- **推定時間**: 2時間（1日）
- **ブランチ**: `refactor/voice-cog-service-integration`
- **Issue**: #73 (Projectに登録済み)

**Task 3.8.3: リグレッションテスト**
- [ ] 既存Voice cogのテストを全て実行
- [ ] リファクタリング前後の動作比較・検証
- [ ] **デグレード（既存機能劣化）が発生していないことを確認**
- [ ] **⚠️ このステップ完了まで新機能開発に進まない**
- **完了条件**: 既存機能に影響がないことが保証される
- **依存**: Task 3.8.2
- **推定時間**: 1時間
- **ブランチ**: `test/regression-voice-cog`
- **Issue**: #73 (Projectに登録済み)

##### 🚀 フェーズ2: テキストメッセージ処理機能の実装

**Task 3.8.4: TextCog作成**
- [ ] src/cogs/text.py作成
- [ ] テキストメッセージ処理専用のCogクラス実装
- [ ] NoteProcessingServiceとの連携基盤構築
- **完了条件**: テキスト処理専用Cogが作成される
- **依存**: Task 3.8.3（リグレッションテスト完了）
- **推定時間**: 2時間（1日）
- **ブランチ**: `feature/text-cog-foundation`
- **Issue**: #74 (Projectに登録済み)

**Task 3.8.5: コアロジック実装**
- [ ] handle_text_messageメソッド実装
- [ ] _format_fleeting_noteメソッド実装
- [ ] NoteProcessingService + ObsidianGitHubServiceの連携
- [ ] Fleeting Note形式への変換処理
- **完了条件**: テキストメッセージがFleeting Note形式に変換される
- **依存**: Task 3.8.4
- **推定時間**: 3時間（1.5日）
- **ブランチ**: `feature/text-message-core-logic`
- **Issue**: #74 (Projectに登録済み)

**Task 3.8.6: エラーハンドリング・ユーザーフィードバック**
- [ ] API呼び出し失敗時のエラー処理
- [ ] ユーザーへの成功/失敗通知メッセージ
- [ ] Ephemeral Messageによる処理状況通知
- [ ] レート制限・タイムアウト対応
- **完了条件**: ユーザーに適切なフィードバックが提供される
- **依存**: Task 3.8.5
- **推定時間**: 2時間（1日）
- **ブランチ**: `feature/text-message-error-handling`
- **Issue**: #74 (Projectに登録済み)

##### 🎯 フェーズ3: インターフェースと統合

**Task 3.8.7: /note Slash Command実装**
- [ ] /note コマンドの実装
- [ ] テキスト長制限（4000文字）とバリデーション
- [ ] TextCogコアロジックとの連携
- [ ] 非同期処理とユーザーフィードバック
- **完了条件**: /noteコマンドが完全に動作する
- **依存**: Task 3.8.6
- **推定時間**: 2時間（1日）
- **ブランチ**: `feature/slash-command-note`
- **Issue**: #75 (Projectに登録済み)

**Task 3.8.8: 統合テスト実装**
- [ ] End-to-Endテストシナリオ作成
- [ ] /noteコマンド実行からGitHubファイル保存までの全体フロー
- [ ] エラー時のフォールバック確認
- [ ] 既存機能との互換性テスト
- [ ] テストカバレッジ70%以上の達成
- **完了条件**: テキストメッセージ機能のE2Eテストが成功
- **依存**: Task 3.8.7
- **推定時間**: 2時間（1日）
- **ブランチ**: `test/text-message-e2e`
- **Issue**: #76 (Projectに登録済み)

#### 🎯 改善されたタスク分解の利点
- **✅ リスク軽減**: 既存Voice機能のデグレード完全防止
- **✅ 管理しやすさ**: 各タスク1-2日の適切なサイズ
- **✅ 段階的検証**: フェーズごとの動作確認
- **✅ 品質保証**: リグレッションテストによる安全性確保
- **✅ 並行開発可能**: フェーズ1完了後、フェーズ2と他タスクの並行実行

#### Task 3.9: Railway CD設定
- [ ] .github/workflows/deploy.ymlの作成
- [ ] Railway CLI設定
- [ ] 環境変数管理
- [ ] デプロイメントトリガー設定
- **完了条件**: mainブランチプッシュで自動デプロイ
- **依存**: なし
- **推定時間**: 2時間
- **ブランチ**: `ci/railway-deployment`

#### Task 3.10: GitHubServiceのテスト
- [ ] tests/test_github_service.pyの作成
- [ ] モックGitHub APIレスポンス
- [ ] レート制限テスト
- [ ] キャッシュテスト
- **完了条件**: GitHubServiceカバレッジ80%以上
- **依存**: Task 3.5
- **推定時間**: 3時間
- **ブランチ**: `test/github-service`

#### Task 3.11: 統合テスト（GitHub機能）
- [ ] End-to-End PR作成テスト
- [ ] エラーリカバリーテスト
- [ ] 並行実行テスト
- [ ] 実際のテストリポジトリでの検証
- **完了条件**: GitHub連携が安定動作する
- **依存**: Task 3.9
- **推定時間**: 3時間
- **ブランチ**: `test/github-integration`

### Phase 4: PKM機能「自分の第二の脳を育てるBot」（12週間）

#### Phase 4.1: 基盤構築（週1-3）

#### Task 4.1.1: ServiceContainer Phase 4拡張
- [ ] Phase 4新規サービス用ServiceContainer拡張実装
- [ ] KnowledgeManager、EmbeddingService、ChromaDBService等の依存関係注入対応
- [ ] 既存サービスとの互換性維持確認
- [ ] 初期化順序とライフサイクル管理実装
- **完了条件**: Phase 4サービスが正常に登録・取得できること
- **依存**: なし
- **推定時間**: 8時間
- **ブランチ**: `refactor/service-container-phase4`

#### Task 4.1.2: BotConfig Gemini・ChromaDB設定追加
- [ ] Gemini API設定項目追加（api_key, monthly_limit等）
- [ ] ChromaDB設定項目追加（persist_directory, collection_name等）
- [ ] PKM機能設定項目追加（hybrid_search_alpha等）
- [ ] API移行モード設定（openai/gemini/hybrid）
- [ ] Pydantic バリデーション追加
- **完了条件**: 全Phase 4設定が環境変数から正常に読み込まれること
- **依存**: なし
- **推定時間**: 4時間
- **ブランチ**: `feature/config-phase4-settings`

#### Task 4.1.3: データベーススキーマ拡張
- [ ] knowledge_notes テーブル作成
- [ ] note_links テーブル作成
- [ ] token_usage テーブル作成
- [ ] 既存transcriptionsテーブル拡張（note_id, tags, links列追加）
- [ ] FTS5検索インデックス構築
- [ ] マイグレーション機能実装
- **完了条件**: 新規テーブルとインデックスが正常に作成されること
- **依存**: なし
- **推定時間**: 6時間
- **ブランチ**: `feature/database-schema-extension`

#### Task 4.1.4: TokenManager実装
- [ ] Gemini API月100万トークン制限管理実装
- [ ] 使用量記録・追跡機能
- [ ] 90%/95%/100%段階制限機能
- [ ] トークン消費量予測機能
- [ ] アラート・通知機能
- **完了条件**: トークン制限が正常に機能すること
- **依存**: Task 4.1.3
- **推定時間**: 8時間
- **ブランチ**: `feature/token-manager`

#### Task 4.1.5: EmbeddingService (Gemini API統合)
- [ ] Gemini API クライアント実装
- [ ] text-embedding-004 モデル統合
- [ ] バッチ埋め込み処理実装
- [ ] エラーハンドリング・リトライ機能
- [ ] キャッシュ機能実装
- **完了条件**: Gemini API埋め込み生成が正常に動作すること
- **依存**: Task 4.1.2, Task 4.1.4
- **推定時間**: 12時間
- **ブランチ**: `feature/gemini-embedding-service`

#### Task 4.1.6: ChromaDBService実装
- [ ] ChromaDB in-process統合実装
- [ ] PersistentClient初期化とコレクション管理
- [ ] ドキュメント追加・更新・削除機能
- [ ] ベクトル検索機能実装
- [ ] Railway永続化対応（Persistent Volumes）
- **完了条件**: ChromaDB操作が全て正常に動作すること
- **依存**: Task 4.1.2
- **推定時間**: 10時間
- **ブランチ**: `feature/chromadb-service`

#### Task 4.1.7: Railway Persistent Volumes設定・検証
- [ ] railway.toml設定更新
- [ ] Dockerfile永続化対応修正
- [ ] データディレクトリ権限設定
- [ ] 起動時整合性チェック実装
- [ ] バックアップ・復元機能基盤
- **完了条件**: Railway環境でデータが永続化されること
- **依存**: Task 4.1.6
- **推定時間**: 6時間
- **ブランチ**: `ci/railway-persistent-volumes`

#### Task 4.1.8: SyncManager基本機能
- [ ] SQLite-ChromaDB同期管理実装
- [ ] ノート変更時の自動同期
- [ ] データ整合性チェック機能
- [ ] 一括同期（bulk_sync）実装
- [ ] 同期エラー処理・復旧機能
- **完了条件**: SQLite-ChromaDB間のデータ同期が正常に動作すること
- **依存**: Task 4.1.3, Task 4.1.5, Task 4.1.6
- **推定時間**: 12時間
- **ブランチ**: `feature/sync-manager-basic`

#### Phase 4.2: PKM機能実装（週4-6）

#### Task 4.2.1: KnowledgeManager中核実装
- [ ] 個人知識管理の中核クラス実装
- [ ] ノートCRUD操作（create_note, update_note, delete_note）
- [ ] リンク抽出機能（[[note_name]]パターン）
- [ ] タグ管理機能
- [ ] ObsidianGitHubService統合（GitHub保存）
- **完了条件**: 基本的なノート管理が全て動作すること
- **依存**: Task 4.1.1, Task 4.1.5, Task 4.1.6, Task 4.1.8
- **推定時間**: 16時間
- **ブランチ**: `feature/knowledge-manager-core`

#### Task 4.2.2: SearchEngine基本実装
- [ ] ベクトル検索機能実装
- [ ] FTS5キーワード検索機能実装
- [ ] 基本検索結果統合
- [ ] 検索結果ランキング機能
- [ ] 検索履歴管理
- **完了条件**: ベクトル・キーワード検索が正常に動作すること
- **依存**: Task 4.2.1
- **推定時間**: 12時間
- **ブランチ**: `feature/search-engine-basic`

#### Task 4.2.3: PKMCog基本コマンド実装
- [ ] /note コマンド実装（ノート作成）
- [ ] /search コマンド実装（基本検索）
- [ ] /list コマンド実装（ノート一覧）
- [ ] Discord UI実装（Embed, View）
- [ ] エラーハンドリング・ユーザーフィードバック
- **完了条件**: 基本PKMコマンドが全て動作すること
- **依存**: Task 4.2.1, Task 4.2.2
- **推定時間**: 14時間
- **ブランチ**: `feature/pkm-basic-commands`

#### Task 4.2.4: ハイブリッド検索実装
- [ ] RRF (Reciprocal Rank Fusion) アルゴリズム実装
- [ ] ベクトル・キーワード検索結果の重み付け統合
- [ ] 検索精度調整・チューニング機能
- [ ] 検索モード選択（vector/keyword/hybrid）
- [ ] パフォーマンス最適化
- **完了条件**: ハイブリッド検索で高精度な結果が得られること
- **依存**: Task 4.2.2
- **推定時間**: 10時間
- **ブランチ**: `feature/hybrid-search-rrf`

#### Task 4.2.5: ノートリンク機能実装
- [ ] [[note_name]]リンク解析・検証
- [ ] 双方向リンク管理
- [ ] リンク先ノート自動検索・提案
- [ ] リンクグラフ可視化（基本）
- [ ] 孤立ノート検出機能
- **完了条件**: ノート間リンクが正常に機能すること
- **依存**: Task 4.2.1
- **推定時間**: 8時間
- **ブランチ**: `feature/note-links`

#### Task 4.2.6: Gemini Audio API移行 (VoiceCog統合)
- [ ] Gemini 1.5 Pro音声転写統合
- [ ] OpenAI Whisper→Gemini移行実装
- [ ] アダプター層実装（段階的切り替え）
- [ ] VoicecogのGemini統合
- [ ] 音声→自動PKMノート化機能
- **完了条件**: Gemini音声転写が正常に動作すること
- **依存**: Task 4.1.5, Task 4.2.1
- **推定時間**: 10時間
- **ブランチ**: `feature/gemini-audio-migration`

#### Phase 4.3: 高度機能・最適化（週7-9）

#### Task 4.3.1: /merge コマンド実装
- [ ] 複数ノート選択UI実装
- [ ] Gemini APIによる知的統合処理
- [ ] 類似ノート自動検出・提案
- [ ] 統合結果のプレビュー・編集機能
- [ ] 統合履歴管理
- **完了条件**: ノート統合が高品質で動作すること
- **依存**: Task 4.2.1, Task 4.2.4
- **推定時間**: 14時間
- **ブランチ**: `feature/merge-command`

#### Task 4.3.2: 自動タグ付け・カテゴリ化
- [ ] Gemini APIによる自動タグ抽出
- [ ] 既存タグとの統合・正規化
- [ ] カテゴリ階層管理
- [ ] タグ推薦システム
- [ ] タグベース検索フィルター
- **完了条件**: 自動タグ付けが実用的レベルで動作すること
- **依存**: Task 4.2.1
- **推定時間**: 10時間
- **ブランチ**: `feature/auto-tagging`

#### Task 4.3.3: Fleeting Note処理拡張
- [ ] 音声メッセージ自動PKM化
- [ ] FleetingNoteView拡張（PKM統合）
- [ ] 自動関連ノート検索・提案
- [ ] Fleeting→Permanent変換支援
- [ ] メタデータ自動抽出
- **完了条件**: 音声からのPKM化が自動で動作すること
- **依存**: Task 4.2.6, Task 4.3.2
- **推定時間**: 8時間
- **ブランチ**: `feature/enhanced-fleeting-notes`

#### Task 4.3.4: バッチ処理最適化
- [ ] 大量ノート一括埋め込み処理
- [ ] ChromaDBバッチ操作最適化
- [ ] メモリ使用量最適化
- [ ] 並列処理実装
- [ ] 処理進捗表示・キャンセル機能
- **完了条件**: 大量データ処理が効率的に動作すること
- **依存**: Task 4.2.1, Task 4.2.4
- **推定時間**: 8時間
- **ブランチ**: `refactor/batch-processing`

#### Task 4.3.5: API制限時フォールバック機能
- [ ] 段階的機能制限システム実装
- [ ] ローカルキャッシュ活用機能
- [ ] 使用量閾値監視・アラート
- [ ] 手動モード・緊急時対応
- [ ] 制限状況UI表示
- **完了条件**: API制限時でも基本機能が維持されること
- **依存**: Task 4.1.4
- **推定時間**: 10時間
- **ブランチ**: `feature/api-fallback-system`

#### Phase 4.4: 品質保証・運用（週10-12）

#### Task 4.4.1: Phase4Monitor・メトリクス
- [ ] PKM機能専用監視システム実装
- [ ] トークン使用量・検索精度メトリクス
- [ ] システム健全性チェック
- [ ] パフォーマンス監視
- [ ] /stats コマンド実装（ダッシュボード）
- **完了条件**: 包括的な監視・メトリクス機能が動作すること
- **依存**: Task 4.1.4, Task 4.2.4
- **推定時間**: 8時間
- **ブランチ**: `feature/phase4-monitoring`

#### Task 4.4.2: AlertManager・通知システム
- [ ] アラート・通知システム実装
- [ ] トークン制限・システム異常通知
- [ ] Discord管理者通知機能
- [ ] アラート設定・閾値管理
- [ ] 通知履歴・分析機能
- **完了条件**: 重要なシステム状態が適切に通知されること
- **依存**: Task 4.4.1
- **推定時間**: 6時間
- **ブランチ**: `feature/alert-manager`

#### Task 4.4.3: BackupManager実装
- [ ] 日次自動バックアップシステム
- [ ] SQLite・ChromaDBデータバックアップ
- [ ] バックアップ世代管理・クリーンアップ
- [ ] 災害復旧手順実装
- [ ] バックアップ整合性チェック
- **完了条件**: データバックアップ・復旧が確実に動作すること
- **依存**: Task 4.1.6, Task 4.1.7
- **推定時間**: 10時間
- **ブランチ**: `feature/backup-manager`

#### Task 4.4.4: PrivacyManager・セキュリティ強化
- [ ] 個人情報検出・マスキング機能
- [ ] 機密情報パターン検出
- [ ] ローカル実行保証強化
- [ ] データ暗号化（必要時）
- [ ] セキュリティ監査ログ
- **完了条件**: プライバシー・セキュリティが確保されること
- **依存**: Task 4.2.1
- **推定時間**: 8時間
- **ブランチ**: `feature/privacy-manager`

#### Task 4.4.5: 統合テスト・品質検証
- [ ] Phase 4機能の包括的統合テスト
- [ ] パフォーマンス・負荷テスト
- [ ] API制限シナリオテスト
- [ ] データ整合性長期テスト
- [ ] ユーザビリティテスト
- **完了条件**: 全機能が本番レベルで安定動作すること
- **依存**: Task 4.4.1, Task 4.4.2, Task 4.4.3, Task 4.4.4
- **推定時間**: 12時間
- **ブランチ**: `test/phase4-integration`

#### Task 4.4.6: ドキュメント・リリース準備
- [ ] Phase 4機能ドキュメント作成
- [ ] API仕様書更新
- [ ] ユーザーマニュアル作成
- [ ] セットアップガイド更新
- [ ] OSS公開準備（README, CONTRIBUTING等）
- **完了条件**: 完全なドキュメントが整備されること
- **依存**: Task 4.4.5
- **推定時間**: 8時間
- **ブランチ**: `docs/phase4-documentation`

#### 追加タスク（Phase 4.5: 拡張機能）

#### Task 4.5.1: /edit コマンド実装
- [ ] ノートID指定編集機能
- [ ] ファジー検索による編集対象選択
- [ ] インライン編集UI実装
- [ ] 編集履歴管理
- [ ] 変更差分表示
- **完了条件**: ノート編集が使いやすく動作すること
- **依存**: Task 4.2.3
- **推定時間**: 8時間
- **ブランチ**: `feature/edit-command`

#### Task 4.5.2: /review コマンド群実装
- [ ] /review daily - 日次レビュー機能
- [ ] /review weekly - 週次知識整理
- [ ] /review monthly - 月次成長分析
- [ ] カスタム期間レビュー機能
- [ ] レビュー結果可視化
- **完了条件**: 定期レビュー機能が実用的に動作すること
- **依存**: Task 4.2.3, Task 4.3.1
- **推定時間**: 10時間
- **ブランチ**: `feature/review-commands`

### Phase 5: 運用基盤完成 + 本格運用（2週間）

#### Task 5.1: VoiceCog設計
- [ ] src/cogs/voice.pyの構造設計
- [ ] OpenAI API統合設計
- [ ] 音声ファイル処理フロー設計
- [ ] エラーハンドリング設計
- **完了条件**: 音声処理アーキテクチャが定義される
- **依存**: Phase 4完了
- **推定時間**: 2時間

#### Task 5.2: OpenAI API統合
- [ ] openai依存関係追加
- [ ] Whisper API呼び出し実装
- [ ] GPT API呼び出し実装
- [ ] レート制限とエラー処理
- **完了条件**: OpenAI APIが利用可能
- **依存**: Task 5.1
- **推定時間**: 3時間

#### Task 5.3: 音声メッセージ処理
- [ ] 音声ファイルダウンロード処理
- [ ] 一時ファイル管理
- [ ] Whisper文字起こし実装
- [ ] GPT整形処理実装
- **完了条件**: 音声が文字起こしされる
- **依存**: Task 5.2
- **推定時間**: 4時間
- **ブランチ**: `feature/voice-transcription`

#### Task 5.4: ヘルスチェック実装
- [ ] /healthエンドポイント設計
- [ ] 簡易HTTPサーバー実装
- [ ] システム状態チェック
- [ ] Railway統合
- **完了条件**: 外部監視が可能
- **依存**: なし
- **推定時間**: 2時間
- **ブランチ**: `feature/health-monitoring`

#### Task 5.5: メトリクス収集
- [ ] 実行時間記録
- [ ] エラー率計測
- [ ] メモリ使用量監視
- [ ] ログへの出力
- **完了条件**: パフォーマンスが可視化される
- **依存**: Task 5.4
- **推定時間**: 3時間
- **ブランチ**: `feature/performance-metrics`

#### Task 5.6: ドキュメント整備
- [ ] APIドキュメント生成
- [ ] デプロイメントガイド作成
- [ ] トラブルシューティングガイド
- [ ] コントリビューションガイド
- **完了条件**: 開発者向けドキュメント完備
- **依存**: なし
- **推定時間**: 4時間
- **ブランチ**: `docs/documentation-complete`

#### Task 5.7: パフォーマンス最適化
- [ ] 非同期処理の最適化
- [ ] メモリリーク調査
- [ ] キャッシュ戦略の調整
- [ ] データベースインデックス最適化
- **完了条件**: 応答時間が目標値以内
- **依存**: Task 5.5
- **推定時間**: 3時間
- **ブランチ**: `refactor/performance-optimization`

#### Task 5.8: セキュリティ強化
- [ ] 入力検証の強化
- [ ] ログマスキング実装
- [ ] 権限管理の徹底
- [ ] セキュリティ監査
- **完了条件**: セキュリティ脆弱性がない
- **依存**: なし
- **推定時間**: 3時間
- **ブランチ**: `refactor/security-hardening`

#### Task 5.9: 本番環境テスト
- [ ] 負荷テスト実施
- [ ] 障害復旧テスト
- [ ] バックアップ・リストアテスト
- [ ] モニタリング動作確認
- **完了条件**: 本番運用の準備完了
- **依存**: Task 5.7, Task 5.8
- **推定時間**: 3時間
- **ブランチ**: `test/production-readiness`

#### Task 5.10: リリース準備
- [ ] バージョンタグ付け
- [ ] リリースノート作成
- [ ] デプロイメントチェックリスト
- [ ] 運用手順書の最終確認
- **完了条件**: v2.0.0リリース可能
- **依存**: Task 5.9
- **推定時間**: 2時間
- **ブランチ**: `release/v2.0.0`

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

**🚨 重要: GitHub Project Issue Status更新**
ブランチ作成と同時に、対応するIssueのステータスを更新：
```bash
# 対象IssueをGitHub ProjectでTodo → In Progressに変更
# 例: Task 4.1.1開始時
gh project item-edit --id [PROJECT_ITEM_ID] \
  --field-id "PVTSSF_lAHOAVzM6c4BAoYLzgzYKtg" \
  --single-select-option-id "47fc9ee4" \
  --project-id "PVT_kwHOAVzM6c4BAoYL"
```

または、GitHub UI上でプロジェクトボードの該当IssueをTodo列からIn Progress列にドラッグ

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

**🚨 重要: 完了時のGitHub Project Status更新**
PRマージ完了と同時に、IssueステータスをDoneに更新：
```bash
# マージ完了後、In Progress → Doneに変更
gh project item-edit --id [PROJECT_ITEM_ID] \
  --field-id "PVTSSF_lAHOAVzM6c4BAoYLzgzYKtg" \
  --single-select-option-id "98236657" \
  --project-id "PVT_kwHOAVzM6c4BAoYL"
```

または、GitHub UI上でプロジェクトボードの該当IssueをIn Progress列からDone列にドラッグ

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
