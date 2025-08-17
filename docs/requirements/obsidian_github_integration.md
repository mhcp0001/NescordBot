# 要件定義書 - Obsidian連携のGitHub統合（Fleeting Note特化）

## 1. 目的

現在ローカルファイルシステムに直接保存しているObsidian vault連携機能を、GitHubリポジトリ（`https://github.com/mhcp0001/obsidian-vault`）に格納されたObsidian vaultと連携するように変更する。Discord上のコンテンツを既存のFleeting note仕様に完全準拠した形で保存し、Zettelkastenワークフローをサポートする。

## 2. 機能要件

### 2.1 必須機能

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

### 2.2 削除する機能

- ❌ **デイリーノート機能** (`/obsidian-daily-note`) - 既存ファイル編集のため削除
- ❌ **添付ファイル保存機能** - Fleeting note特化のため削除

## 3. Git操作の詳細仕様

### 3.1 リポジトリ管理戦略

#### Shallow Clone戦略
- **採用理由**: 新規ファイル作成のみのため、過去の履歴は不要
- **実装**: `git clone --depth=1 <repository_url>`
- **更新**: `git fetch --depth=1` + `git reset --hard origin/main`

#### リポジトリ保存場所
- **ローカルパス**: `./data/obsidian_vault/`
- **永続化**: Railway環境では永続ボリュームにマウント
- **権限**: Bot専用ディレクトリで他プロセスからの干渉を防止

### 3.2 Git操作のフロー

#### 基本操作シーケンス
```
1. git stash push (ローカル変更を退避)
2. git pull --rebase (リモート最新を取得)
3. git stash pop (変更を復旧)
4. ファイル作成・追加
5. git add .
6. git commit -m "message"
7. git push origin main
```

#### エラーハンドリング
- **detached HEAD復旧**: `git switch main`で復旧
- **ロックファイル削除**: `.git/index.lock`の起動時チェック・削除
- **競合発生**: 自動解決を試みず、管理者通知後にキューに戻して後でリトライ

### 3.3 非同期処理の実装

- **Git操作**: `asyncio.to_thread()`でThreadPoolExecutorを使用
- **理由**: Gitコマンドはブロッキング操作のため、イベントループを妨げないよう別スレッドで実行
- **同時実行制御**: `asyncio.Lock`によるアトミック操作保証

## 4. SQLite永続化キューの実装

### 4.1 データベーススキーマ

#### キューテーブル
```sql
CREATE TABLE queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    priority INTEGER DEFAULT 0 NOT NULL,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL
        CHECK(status IN ('pending', 'processing', 'failed', 'completed')),
    idempotency_key TEXT UNIQUE,  -- DiscordメッセージIDなど
    payload JSON NOT NULL,
    last_error TEXT
);

-- 効率的なキューイングのためのインデックス
CREATE INDEX idx_queue_polling ON queue (status, priority, created_at);
```

#### デッドレターキューテーブル
```sql
CREATE TABLE dead_letter_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_queue_id INTEGER,
    created_at TIMESTAMP NOT NULL,
    moved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retry_count INTEGER NOT NULL,
    payload JSON NOT NULL,
    last_error TEXT NOT NULL
);
```

### 4.2 キュー操作のロジック

#### タスクの投入
```python
async def enqueue_task(payload: dict, idempotency_key: str) -> None:
    # 重複チェック + キューへの投入
    # JSONペイロードにメッセージ情報を格納
```

#### タスクの処理
```python
async def process_queue() -> None:
    # 1. pendingステータスのタスクを優先度・作成日時順で取得
    # 2. ステータスをprocessingに更新
    # 3. Git操作実行
    # 4. 成功: completed / 失敗: retry_count++またはDLQへ移動
```

#### 復旧処理
- **Bot起動時**: `processing`状態で`updated_at`が5分以上古いタスクを`pending`に戻す
- **目的**: Bot異常終了時の処理中タスクの救済

### 4.3 デッドレターキュー（DLQ）

#### 移動条件
- `retry_count >= 5`のタスク
- 恒久的エラー（認証失敗等）が検出されたタスク

#### 管理者通知
- DLQへの移動時にDiscordへ通知
- 定期的なDLQ蓄積状況の報告

## 5. Fleeting Note仕様（既存vault準拠）

### 5.1 ファイル構造

#### 保存場所
- **ディレクトリ**: `Fleeting Notes/`

#### ファイル命名規則（既存仕様維持）
- **Discord メッセージ**: `YYYYMMDD_HHMM_discord_message_[user_name].md`
- **音声文字起こし**: `YYYYMMDD_HHMM_voice_transcript_[user_name].md`

#### 重複回避策
1. **秒単位追加**: `YYYYMMDD_HHMMSS_discord_message_[user_name].md`
2. **連番追加**: `YYYYMMDD_HHMMSS_discord_message_[user_name]_001.md`
3. **ファイル存在チェック**: 作成前に存在確認し、重複時は自動的に連番付与

#### メタデータ（YAML frontmatter）
```yaml
---
# ●基本情報
id: YYYYMMDDHHMMSS
title: "[自動生成タイトル]"

# ●分類と状態
type: fleeting_note
status: fleeting # [fleeting, processing, archived]
tags:
  - capture/
  - discord/

# ●関連情報
context: "[Discord context]"
source: "Discord Bot NescordBot"
created: YYYY-MM-DD HH:MM
---
```

#### コンテンツ構造
```markdown
# [タイトル]

## 💭 アイデア・思考の断片

[Discord メッセージ内容 または 音声文字起こし内容]

## 🔗 関連しそうなこと
-

## ❓ 疑問・調べたいこと
-

## 📝 次のアクション
- [ ] Literature Noteに発展させる
- [ ] Permanent Noteに昇華する
- [ ] 関連資料を調査する
- [ ] アーカイブする

---

### Discord情報
- **サーバー**: [server_name]
- **チャンネル**: [channel_name]
- **ユーザー**: [user_name]
- **メッセージID**: [message_id]
- **URL**: [discord_message_url]

---
*素早く記録することを優先。後で整理・発展させる。*
```

### 5.2 自動生成ルール

#### タイトル生成
- **メッセージ**: メッセージ冒頭20文字 + "..."
- **音声**: "音声メモ: [冒頭15文字]..."

#### Tags自動付与
- `capture/` (必須)
- `discord/` (必須)
- `discord/[channel_name]` (チャンネル別)
- `voice/` (音声の場合)

#### Context自動設定
- **メッセージ**: "Discord #[channel_name]での会話"
- **音声**: "Discord #[channel_name]での音声メッセージ"

## 6. バッチ処理とパフォーマンス最適化

### 6.1 バッチ処理戦略

#### バッチ実行条件
- **時間ベース**: 最後の処理から5秒経過
- **件数ベース**: キューに10件蓄積
- **いずれかの条件を満たした時点で実行**

#### バッチ処理のメリット
- Git操作のオーバーヘッド削減
- ネットワーク通信の効率化
- リポジトリ肥大化の抑制（複数ファイルを1コミットにまとめる）

### 6.2 パフォーマンス考慮事項

#### 想定利用規模
- 同時接続ユーザー: 50-100人
- 1日のメッセージ数: 500-1000件
- vault内のファイル数: 10,000件

#### ボトルネック対策
- **Git操作**: バッチ処理で頻度を削減
- **SQLite書き込み**: WALモード有効化
- **検索性能**: FTS5インデックスの構築

## 7. 検索機能の実装

### 7.1 SQLite FTS5を使った全文検索

#### インデックステーブル
```sql
CREATE VIRTUAL TABLE notes_fts USING fts5(
    file_path,
    title,
    content,
    tags,
    tokenize='unicode61'
);
```

#### 日本語対応
- **初期実装**: `unicode61`で基本的な検索
- **将来拡張**: MeCabやSudachiPyによる形態素解析（必要に応じて）

#### インデックス更新
- **タイミング**: ファイル作成・Git push成功後に即座に更新
- **理由**: ユーザーが作成後すぐに検索できることを重視

## 8. リスク評価マトリクス

| 機能項目 | リスク | 実装難易度 | 対策 |
|---------|--------|------------|------|
| **Git基本操作** | 中 | 中 | エラーハンドリングとリトライロジックの実装 |
| **detached HEAD復旧** | 高 | 高 | 起動時の状態チェックと自動復旧処理 |
| **SQLiteキュー** | 低 | 低 | WALモードとaiosqliteの適切な使用 |
| **永続化キュー復旧** | 中 | 中 | processing状態の検出と安全な復旧ロジック |
| **FTS5基本検索** | 中 | 中 | unicode61トークナイザーで十分 |
| **日本語形態素解析** | 高 | 高 | MeCab/Sudachi導入の複雑性 |
| **メトリクス公開** | 中 | 中 | Railway環境でのポート設定とセキュリティ |

## 9. 非機能要件

### 9.1 パフォーマンス要件

- **応答時間**: Discord コマンドの初期応答3秒以内
- **バッチ処理**: 10件の変更を30秒以内に処理
- **Git操作**: 95パーセンタイルで15秒以内にpush完了
- **検索応答**: 1万ファイル規模で2秒以内

### 9.2 信頼性要件

#### エラーハンドリングシナリオ
1. **detached HEAD状態**: `git switch main`による自動復旧
2. **マージコンフリクト**: 処理中断→管理者通知→手動解決待ち
3. **DB破損**: バックアップからの復旧またはDLQからの再処理
4. **Railway再起動**: 永続ボリュームによるデータ保持

#### データ損失許容範囲
- **メッセージ損失**: 一切許容しない（永続化キューによる保証）
- **DLQ移動**: 手動復旧を前提とするが、データ自体は保持

### 9.3 セキュリティ要件

#### GitHub認証管理
- **本番環境**: GitHub App認証（推奨）
- **開発環境**: Personal Access Token（許容）
- **秘密鍵ローテーション**: 3-6ヶ月ごとの定期実施

#### 入力サニタイゼーション
- **ファイル名**: `pathvalidate`ライブラリによる安全化
- **コンテンツ**: XSS対策（将来のWeb表示を考慮）
- **コマンドインジェクション**: `shell=False`必須、引数リスト渡し

### 9.4 運用・監視要件

#### ログ管理
- **構造化ログ**: `structlog`によるJSON形式
- **ログレベル**: INFO（本番）、DEBUG（問題調査時）
- **ログローテーション**: Railway提供機能または外部サービス

#### メトリクス収集
```python
# 基本メトリクス
notes_created_total = Counter('nescordbot_notes_created_total', ['result'])
git_operations_duration = Histogram('nescordbot_git_operation_seconds', ['operation'])
queue_size = Gauge('nescordbot_queue_size', ['status'])
```

#### エラー通知戦略
- **重要度分類**: Critical（即座通知）、Warning（集約通知）
- **通知集約**: 同一エラーの繰り返し防止
- **通知先**: 専用Discordチャンネル

## 10. 運用課題への対策

### 10.1 ログの肥大化
- **対策**: 構造化ログ + 外部ログ収集サービス（Papertrail等）
- **ローテーション**: 定期的な古いログの削除

### 10.2 エラー通知の過多
- **対策**: Sentryによるエラー集約とアラート制御
- **通知レベル**: 一時的エラーはログのみ、恒久的エラーのみ通知

### 10.3 Git履歴の肥大化
- **対策**: shallow cloneの継続使用
- **コミット戦略**: 意味のあるまとまりでのコミット作成

### 10.4 SQLiteデータベースの肥大化
- **対策**:
  - 完了タスクの定期削除
  - 週次での`VACUUM`実行
  - アーカイブテーブルへの履歴移動

## 11. 実装フェーズ（改訂版）

### Phase 1: 基盤構築（1-1.5週間）
- [ ] **目標**: 1つのメッセージを安全にファイル化
- [ ] SQLite永続化キューの基本実装
- [ ] Git操作の非同期ラッパー（最低限のエラー処理付き）
- [ ] Discordコマンドとキューイング機能
- [ ] バックグラウンドタスクによるキュー処理

### Phase 2: 堅牢化と実用化（1週間）
- [ ] **目標**: 連続メッセージの安定処理
- [ ] リトライロジック（指数バックオフ）の実装
- [ ] デッドレターキューの実装
- [ ] processing状態復旧ロジック
- [ ] Railway環境での永続ボリューム設定

### Phase 3: 高度化と監視（1週間）
- [ ] **目標**: 運用を見据えた機能完成
- [ ] Prometheusメトリクス収集
- [ ] FTS5による基本検索機能
- [ ] 管理者向けキュー状態確認コマンド
- [ ] エラー通知とアラート機能

### Phase 4: 最適化と拡張（低優先度）
- [ ] バッチ処理の最適化
- [ ] 日本語形態素解析の検討
- [ ] 詳細なパフォーマンスチューニング
- [ ] 高度な監視・アラート機能

## 12. 環境変数設定

```env
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
```

---

## ✅ 確認済み項目

- **対象リポジトリ**: `https://github.com/mhcp0001/obsidian-vault`
- **vault構造**: リポジトリ全体がvault
- **競合環境**: 高競合（他の人+Obsidianアプリが編集）
- **認証方式**: GitHub App作成可能、開発時PAT許容
- **同期要件**: バッチ処理で十分
- **Fleeting note仕様**: 既存仕様を維持（ファイル命名規則含む）
- **競合回避戦略**: 新規ファイル作成のみに制限
- **Gemini議論**: 実装の詳細・リスク・運用課題を徹底検討済み
