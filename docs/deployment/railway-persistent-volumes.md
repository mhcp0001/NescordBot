# Railway Persistent Volumes 設定ガイド

## 概要

NescordBotでRailway Persistent Volumesを使用してデータ永続化を実現するための完全設定ガイドです。ChromaDBとSQLiteデータベースを永続化し、アプリケーション再起動後もデータを保持します。

## 前提条件

- Railway アカウント（Pro プラン推奨）
- GitHub リポジトリがRailwayにデプロイ済み
- NescordBot Phase 4機能（ChromaDBService、EmbeddingService）が実装済み

## Railway Persistent Volumes とは

Railway Persistent Volumesは、コンテナの再起動やデプロイ後もデータを保持するためのストレージソリューションです。

### 特徴
- **データ永続化**: コンテナが再作成されてもデータが保持
- **高性能**: SSDベースの高速ストレージ
- **自動バックアップ**: Railwayが自動でバックアップを作成
- **容量制限**: プランに応じたストレージ容量制限

## 設定方法

### 1. railway.json設定

プロジェクトルートの`railway.json`に以下を追加：

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "numReplicas": 1,
    "sleepApplication": false,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3,
    "healthcheckTimeout": 300
  },
  "volumes": [
    {
      "mount": "/app/data",
      "name": "nescordbot-data"
    },
    {
      "mount": "/app/chromadb_data",
      "name": "chromadb-persist"
    }
  ]
}
```

### 2. Dockerfile更新

```dockerfile
# データディレクトリ作成と権限設定
RUN mkdir -p /app/data /app/chromadb_data && \
    chmod 755 /app/data /app/chromadb_data

# ボリュームマウントポイント定義
VOLUME ["/app/data", "/app/chromadb_data"]
```

### 3. 環境変数設定

Railway環境で以下の環境変数を設定：

```bash
# データベース設定（永続化ボリューム使用）
DATABASE_URL=sqlite:///app/data/nescordbot.db

# ChromaDB設定（永続化ボリューム使用）
CHROMADB_PERSIST_DIRECTORY=/app/chromadb_data
CHROMADB_COLLECTION_NAME=nescord_knowledge

# その他の必須設定
DISCORD_TOKEN=your_token_here
GEMINI_API_KEY=your_gemini_key_here
```

### 4. Railway ダッシュボード設定

1. **Project Settings → Volumes**
2. **Create Volume**で以下を作成：
   - Volume Name: `nescordbot-data`
   - Mount Path: `/app/data`
   - Size: 1GB（必要に応じて調整）

3. 2つ目のボリューム作成：
   - Volume Name: `chromadb-persist`
   - Mount Path: `/app/chromadb_data`
   - Size: 2GB（埋め込みデータ用）

## データ構造

### ボリューム構成

```
/app/data/                 # SQLiteデータベース用ボリューム
├── nescordbot.db         # メインデータベース
└── backups/              # バックアップファイル
    ├── nescordbot_backup_20250826_120000/
    └── ...

/app/chromadb_data/        # ChromaDBデータ用ボリューム
├── chroma.sqlite3        # ChromaDBメタデータ
├── collections/          # コレクションデータ
│   └── nescord_knowledge/
└── index/               # ベクトルインデックス
```

## 永続化検証

### 自動検証機能

NescordBotは起動時に自動で永続化機能を検証します：

```python
# ChromaDBServiceの永続化検証
async def verify_persistence(self) -> bool:
    """永続化ディレクトリの整合性と機能確認"""
    # 1. ディレクトリ存在確認
    # 2. 書き込み権限確認
    # 3. テストドキュメント作成・削除
    # 4. ChromaDBメタデータ検証
```

### 手動検証方法

Railway環境で以下のコマンドで検証可能：

```bash
# Railway CLI経由でコンテナに接続
railway connect

# ボリュームマウント確認
df -h | grep /app

# データディレクトリ確認
ls -la /app/data /app/chromadb_data

# 書き込みテスト
echo "test" > /app/data/test.txt && rm /app/data/test.txt
```

## バックアップ・復元

### 自動バックアップ

NescordBotには自動バックアップ機能が組み込まれています：

```python
from nescordbot.utils.backup import BackupManager

# フルバックアップ作成
backup_manager = BackupManager(config)
backup_id = await backup_manager.create_full_backup()

# 古いバックアップクリーンアップ（5世代保持）
deleted_count = await backup_manager.cleanup_old_backups(keep_count=5)
```

### 手動バックアップ

```bash
# Railway CLI でバックアップ
railway volume backup nescordbot-data
railway volume backup chromadb-persist

# バックアップ一覧確認
railway volume list-backups
```

### 復元手順

```bash
# 1. Railway ダッシュボードからボリュームバックアップを復元
# 2. アプリケーション再起動
railway restart

# 3. データ整合性確認（ログで確認可能）
railway logs
```

## トラブルシューティング

### よくある問題

#### 1. ボリュームマウントエラー

**症状**: アプリケーション起動時にボリュームマウントに失敗

```
Error: failed to mount volume nescordbot-data
```

**解決方法**:
- Railway ダッシュボードでボリュームが正しく作成されているか確認
- `railway.json`のボリューム設定確認
- プロジェクト再デプロイ

#### 2. 権限エラー

**症状**: ディレクトリへの書き込みができない

```
PermissionError: No write permission to persist directory
```

**解決方法**:
```dockerfile
# Dockerfileに権限設定を追加
RUN chmod 755 /app/data /app/chromadb_data
```

#### 3. データベース接続エラー

**症状**: SQLiteデータベースに接続できない

```
sqlite3.OperationalError: unable to open database file
```

**解決方法**:
- `DATABASE_URL`環境変数の確認
- ボリューマウントパスの確認
- データベースファイルの存在確認

#### 4. ChromaDBデータ紛失

**症状**: アプリケーション再起動後にChromaDBデータがない

**解決方法**:
```bash
# 永続化ディレクトリの確認
ls -la /app/chromadb_data

# ChromaDB設定確認
echo $CHROMADB_PERSIST_DIRECTORY
```

### ログ分析

重要なログメッセージ：

```bash
# 成功時
INFO: ChromaDB service initialized with persist directory: /app/chromadb_data
INFO: ChromaDB persistence verification successful

# エラー時
ERROR: Persist directory does not exist: /app/chromadb_data
ERROR: No write permission to persist directory
ERROR: ChromaDB persistence verification failed
```

## 容量管理

### ストレージ使用量監視

```python
# バックアップマネージャーで容量確認
backup_manager = BackupManager(config)
backups = backup_manager.list_backups()

for backup in backups:
    size_mb = backup['size'] / (1024 * 1024)
    print(f"Backup: {backup['backup_id']}, Size: {size_mb:.2f} MB")
```

### 容量最適化

1. **定期的なクリーンアップ**
   ```python
   # 古いバックアップ削除
   await backup_manager.cleanup_old_backups(keep_count=3)
   ```

2. **ChromaDBコレクションの最適化**
   ```python
   # 不要なドキュメント削除
   await chromadb_service.delete_document(document_id)
   ```

## パフォーマンス最適化

### ChromaDB設定

```python
# 高性能設定
CHROMADB_SETTINGS = {
    "persist_directory": "/app/chromadb_data",
    "anonymized_telemetry": False,
    "allow_reset": True,
}
```

### SQLite最適化

```python
# SQLite接続オプション
DATABASE_URL = "sqlite:///app/data/nescordbot.db?timeout=20&journal_mode=WAL"
```

## セキュリティ考慮事項

### アクセス制御

```dockerfile
# セキュアな権限設定
RUN mkdir -p /app/data /app/chromadb_data && \
    chmod 750 /app/data /app/chromadb_data && \
    chown nobody:nobody /app/data /app/chromadb_data

USER nobody
```

### バックアップ暗号化

```python
# バックアップ時の暗号化（将来実装予定）
await backup_manager.create_encrypted_backup(encryption_key)
```

## 料金情報

Railway Persistent Volumesの料金：

- **容量**: $0.25/GB/月
- **I/O**: 無料（通常使用範囲内）
- **バックアップ**: 自動バックアップ無料

### 推奨容量

- **小規模**: データ 1GB, ChromaDB 1GB (月額 $0.50)
- **中規模**: データ 2GB, ChromaDB 3GB (月額 $1.25)
- **大規模**: データ 5GB, ChromaDB 10GB (月額 $3.75)

## まとめ

Railway Persistent Volumesを使用することで：

✅ **データ永続化**: コンテナ再起動後もデータ保持
✅ **高可用性**: 自動バックアップによるデータ保護
✅ **スケーラビリティ**: 必要に応じた容量拡張
✅ **運用性**: 自動化されたバックアップ・復元機能

これにより、NescordBotのPKM機能が本格的なプロダクション環境で運用可能になります。

## 関連ドキュメント

- [Railway Volumes Documentation](https://docs.railway.app/reference/volumes)
- [NescordBot Phase 4 設計書](../architecture/design/integrated_design_phase4.md)
- [ChromaDB公式ドキュメント](https://docs.trychroma.com/)
- [SQLite WALモード](https://sqlite.org/wal.html)
