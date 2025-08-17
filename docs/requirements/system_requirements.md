# 要件定義書 - NescordBot 総合要件

## プロジェクト概要

NescordBotは音声文字起こしとAI機能を持つDiscord Botです。本要件定義書は、開発・運用基盤の整備とObsidian GitHub統合機能の両方を包含します。

## 関連ドキュメント

- **開発基盤要件**: [requirements_original_development_foundation.md](./requirements_original_development_foundation.md)
- **Obsidian GitHub統合要件**: [requirements_obsidian_github_integration.md](./requirements_obsidian_github_integration.md)

---

# パート1: 基盤整備要件

## 1. 目的

様々な機能を継続的に追加・改善できる拡張性の高いDiscord Botの基盤を構築し、効率的な開発・テスト・デプロイメントワークフローを確立する。**MVPアプローチ**により、機能開発と基盤整備を並行して進め、早期に価値を提供しながら段階的に基盤を強化する。

## 2. 基盤機能要件

### 2.1 Bot基盤アーキテクチャ

- [ ] **モジュラー設計**
  - Cog システムによる機能分離
  - プラグイン方式での機能追加
  - 設定ファイルによる機能のON/OFF切り替え

- [ ] **設定管理システム**
  - 環境別設定（開発・本番）
  - Hot reload 対応
  - バリデーション機能付き設定読み込み

- [ ] **ログ・監視システム**
  - 構造化ログ出力
  - エラー追跡とアラート
  - パフォーマンス監視

- [ ] **データ永続化**
  - データベース設計（SQLite/PostgreSQL）
  - マイグレーション管理
  - バックアップ・復旧機能

- [ ] **外部サービス連携基盤**
  - GitHub API統合モジュール
  - API認証・レート制限管理
  - 外部サービス障害時のフォールバック

### 2.2 開発支援機能

- [ ] **開発環境構築**
  - Docker コンテナ化
  - 開発用設定とシードデータ
  - ローカル開発サーバー

- [ ] **コード品質管理**
  - Linting (flake8, black, isort)
  - 型チェック (mypy)
  - セキュリティ監査

- [ ] **テスト基盤**
  - ユニットテスト環境
  - インテグレーションテスト
  - モック・フィクスチャ整備

### 2.3 CI/CD パイプライン

- [ ] **継続的インテグレーション**
  - GitHub Actions 設定
  - 自動テスト実行
  - コード品質チェック

- [ ] **継続的デプロイメント**
  - 自動デプロイメント
  - 環境別デプロイ戦略
  - ロールバック機能

- [ ] **リリース管理**
  - バージョニング戦略
  - リリースノート自動生成
  - タグ・ブランチ管理

---

# パート2: Obsidian GitHub統合機能要件

## 3. Obsidian連携の目的

現在ローカルファイルシステムに直接保存しているObsidian vault連携機能を、GitHubリポジトリ（`https://github.com/mhcp0001/obsidian-vault`）に格納されたObsidian vaultと連携するように変更する。Discord上のコンテンツを既存のFleeting note仕様に完全準拠した形で保存し、Zettelkastenワークフローをサポートする。

## 4. Obsidian機能要件

### 4.1 必須機能

- [ ] **GitHubリポジトリ連携設定**
  - リポジトリ: `https://github.com/mhcp0001/obsidian-vault`
  - GitHub App認証による安全なアクセス（開発時はPAT許容）
  - リポジトリ全体をvaultとして扱う

- [ ] **Fleeting Note作成機能**
  - Discord メッセージ保存（`/obsidian-save-message`）
  - 音声文字起こし保存（`/obsidian-save-voice`）
  - 既存のFleeting note仕様に完全準拠

- [ ] **読み取り専用機能**
  - ノート検索（`/obsidian-search`）
  - ステータス確認（`/obsidian-status`）

- [ ] **Git操作管理**
  - Bot起動時の自動リポジトリクローン/更新
  - バッチ処理による効率的な同期（新規ファイル作成のみ）
  - 非同期ロックによるアトミックな操作保証

- [ ] **SQLite永続化キュー**
  - 処理キューのデータベース管理
  - Bot再起動時のキュー復旧
  - デッドレターキュー（DLQ）による失敗タスク隔離

- [ ] **エラーハンドリング**
  - GitHub API障害時のローカルキャッシュ保持
  - 指数バックオフによる再試行ロジック
  - 管理者への通知機能（Discord）

### 4.2 削除する機能

- ❌ **デイリーノート機能** (`/obsidian-daily-note`) - 既存ファイル編集のため削除
- ❌ **添付ファイル保存機能** - Fleeting note特化のため削除

### 4.3 Fleeting Note仕様（既存vault準拠）

#### 保存場所・命名規則（既存仕様維持）
- **ディレクトリ**: `Fleeting Notes/`
- **Discord メッセージ**: `YYYYMMDD_HHMM_discord_message_[user_name].md`
- **音声文字起こし**: `YYYYMMDD_HHMM_voice_transcript_[user_name].md`

#### 重複回避策
1. **秒単位追加**: `YYYYMMDD_HHMMSS_discord_message_[user_name].md`
2. **連番追加**: `YYYYMMDD_HHMMSS_discord_message_[user_name]_001.md`
3. **ファイル存在チェック**: 作成前に存在確認し、重複時は自動的に連番付与

#### 競合回避戦略
- **新規ファイル作成**: ✅ Bot が実行
- **既存ファイル読み取り**: ✅ Bot が実行
- **既存ファイル編集**: ❌ Bot は実行しない（競合回避）

## 5. 統合非機能要件

### 5.1 パフォーマンス
- **Bot応答**: Discord コマンドの初期応答3秒以内
- **バッチ処理**: 10件の変更を30秒以内に処理
- **Git操作**: 95パーセンタイルで15秒以内にpush完了
- **検索応答**: 1万ファイル規模で2秒以内
- **大規模vault**: 1万ファイルでも合理的なメモリ使用

### 5.2 セキュリティ
- **認証管理**: GitHub App認証（本番）、PAT（開発時のみ）
- **最小権限**: リポジトリのContents権限のみ
- **秘密鍵管理**: 環境変数またはシークレット管理サービス利用
- **入力サニタイゼーション**: ファイル名・コンテンツの安全化
- **コマンドインジェクション**: shell=False必須、引数リスト渡し

### 5.3 拡張性・保守性
- **モジュラー設計**: Cog システムによる機能分離
- **設定の分離**: GitHub・Obsidian関連設定を環境変数で外部化
- **ログ出力**: Git操作とファイル作成の詳細ログ
- **テスタビリティ**: 外部サービスのモック化対応
- **構造化ログ**: `structlog`によるJSON形式
- **メトリクス収集**: Prometheusメトリクス対応

### 5.4 互換性
- **既存機能**: 現在のコマンドインターフェースは変更しない
- **Obsidian同期**: Obsidianアプリからの編集に影響しない
- **下位互換性**: ローカルvault設定も併存可能

## 6. 制約事項

### 6.1 技術的制約
- **Python**: 3.11+ の使用
- **Discord.py**: 2.3+ の使用
- **依存関係管理**: Poetry
- **Git依存**: 実行環境にgitコマンドラインツールが必要
- **競合環境**: 他の人・Obsidianアプリとの同時編集あり
- **エンコーディング**: UTF-8一貫使用

### 6.2 運用制約
- **24/7稼働**: 継続的な稼働要求
- **レート制限**: Discord・GitHub API制限の遵守
- **デプロイ**: Railway PaaS環境での動作
- **vault仕様準拠**: 既存のFleeting note仕様から逸脱しない

## 7. 成功基準

### 7.1 基盤整備完了の定義
- [ ] モジュラー設計による機能分離
- [ ] 自動テストとコード品質チェック（CI）
- [ ] 構造化ログ出力の実装
- [ ] 開発環境の標準化（Poetry, Docker）
- [ ] 自動デプロイメント（CD）の実装

### 7.2 Obsidian統合完了の定義
- [ ] Discord メッセージ・音声のFleeting note化
- [ ] バッチ処理による安定したGit同期
- [ ] 既存vault仕様への完全準拠
- [ ] 競合回避の確実な動作確認

### 7.3 開発効率の評価基準
- **短期目標**: 小規模な修正を30分以内でテスト・デプロイ
- **中期目標**: 新機能開発のリードタイム半減
- **継続目標**: バグ発生率の低減、運用障害の早期発見

## 8. リスク管理

### 8.1 技術的リスク
- **Git操作の競合**: 複数の非同期リクエストによるリポジトリ破損
  - **対策**: asyncio.Lockによるアトミック操作保証
- **detached HEAD状態**: Git操作の異常による破損状態
  - **対策**: 起動時の状態チェックと自動復旧処理
- **GitHub API障害**: 長時間のサービス停止
  - **対策**: SQLite永続化キューによるデータ保護とローカルキャッシュ
- **SQLiteデータベース破損**: キューデータの損失
  - **対策**: WALモードとバックアップ・復旧機能
- **過度な抽象化**: 複雑性増加による開発速度低下
  - **対策**: YAGNI原則の適用、MVP アプローチの徹底

### 8.2 運用リスク
- **認証情報の管理**: GitHub App秘密鍵の漏洩
  - **対策**: 環境変数管理、定期ローテーション
- **vault仕様変更**: 既存Fleeting note仕様の変更
  - **対策**: 仕様変更検知とBotコード更新プロセス
- **CI/CD 障害**: パイプライン停止による開発停滞
  - **対策**: 手動デプロイ手順の維持、フォールバック戦略

## 9. 実装フェーズ

### Phase 1: MVP基盤 + 既存機能安定化 (2週間)
- **Week 1**: 基本構造整理、基本ログシステム、CI導入
- **Week 2**: 既存機能のリファクタリングと安定化
- **成果物**: 安定動作するBot + 基本的な開発環境

### Phase 2: 開発基盤強化 + GitHub統合準備 (2週間)
- **Week 1**: テスト環境、コード品質ツール、設定管理
- **Week 2**: GitHub App認証とリポジトリアクセス基盤
- **成果物**: 品質保証されたコードベース + GitHub統合基盤

### Phase 3: Obsidian GitHub統合実装 (2週間)
- **Week 1**: Fleeting note作成機能（メッセージ・音声）
- **Week 2**: バッチ処理とキューイング機能、エラーハンドリング
- **成果物**: 完全なObsidian GitHub統合機能

### Phase 4: CD導入 + 運用基盤完成 (2週間)
- **Week 1**: Railway自動デプロイ、環境分離
- **Week 2**: 監視・アラート、ドキュメント整備
- **成果物**: 本番運用可能な完全なBot基盤

### 継続フェーズ: 機能開発サイクル (2週間スプリント)
- 基盤上での新機能継続開発
- 基盤の段階的改善
- Obsidian連携機能の拡張

## 10. 環境変数設定

```env
# Discord
DISCORD_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key

# GitHub統合
GITHUB_OBSIDIAN_REPO_URL=https://github.com/mhcp0001/obsidian-vault
GITHUB_OBSIDIAN_APP_ID=123456
GITHUB_OBSIDIAN_PRIVATE_KEY_PATH=/path/to/private-key.pem

# Git操作設定
OBSIDIAN_REPO_LOCAL_PATH=./data/obsidian_vault
OBSIDIAN_BATCH_SYNC_INTERVAL=5  # seconds
OBSIDIAN_BATCH_SIZE_THRESHOLD=10  # items

# Fleeting Note設定
OBSIDIAN_FLEETING_DIR=Fleeting Notes
OBSIDIAN_MAX_QUEUE_SIZE=100

# エラー処理設定
OBSIDIAN_MAX_RETRY_COUNT=5
OBSIDIAN_RETRY_BACKOFF_MULTIPLIER=2
OBSIDIAN_RETRY_MAX_WAIT=60  # seconds

# 通知設定
OBSIDIAN_ERROR_CHANNEL_ID=1234567890
OBSIDIAN_NOTIFICATION_THROTTLE=300  # seconds

# SQLite設定
OBSIDIAN_DB_PATH=./data/obsidian_queue.db
OBSIDIAN_DB_WAL_MODE=true

# システム設定
LOG_LEVEL=INFO
MAX_AUDIO_SIZE_MB=25
SPEECH_LANGUAGE=ja-JP
```

---

## 関連ドキュメント参照

詳細な要件については、以下の専用ドキュメントを参照してください：

- **[開発基盤要件詳細](./requirements_original_development_foundation.md)**: MVP基盤、CI/CD、アーキテクチャ設計
- **[Obsidian GitHub統合要件詳細](./requirements_obsidian_github_integration.md)**: Fleeting note仕様、Git操作、競合回避戦略
