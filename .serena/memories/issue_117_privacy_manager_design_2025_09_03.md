# Issue #117 PrivacyManager・セキュリティ強化 設計書
## 記録日: 2025-09-03

## 🎯 開発アプローチ

### AlertManagerパターン活用戦略
Issue #115 AlertManager実装で確立した以下のパターンを最大限活用：

1. **Enum-based設定管理**: AlertSeverity → PrivacyLevel, MaskingType
2. **dataclass活用**: Alert/AlertRule → PrivacyRule/SecurityEvent
3. **ServiceContainer統合**: 依存性注入パターン
4. **BotConfig拡張**: 設定項目追加パターン
5. **データベース統合**: テーブル作成・管理パターン
6. **包括的テスト**: 26テストケース構造を参考

## 📋 PrivacyManagerサービス設計

### 核心コンポーネント

#### 1. Enum定義
```python
class PrivacyLevel(Enum):
    NONE = "none"           # マスキングなし
    LOW = "low"             # 部分マスキング
    MEDIUM = "medium"       # 標準マスキング
    HIGH = "high"           # 完全マスキング

class MaskingType(Enum):
    ASTERISK = "asterisk"   # ***で隠す
    PARTIAL = "partial"     # 一部のみ表示
    HASH = "hash"           # ハッシュ化
    REMOVE = "remove"       # 完全削除

class SecurityEventType(Enum):
    PII_DETECTED = "pii_detected"
    API_KEY_EXPOSED = "api_key_exposed"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    ACCESS_VIOLATION = "access_violation"
```

#### 2. データクラス
```python
@dataclass
class PrivacyRule:
    id: str
    name: str
    pattern: str              # 正規表現パターン
    privacy_level: PrivacyLevel
    masking_type: MaskingType
    enabled: bool = True
    description: str = ""

@dataclass
class SecurityEvent:
    id: str
    event_type: SecurityEventType
    message: str
    privacy_level: PrivacyLevel
    timestamp: datetime
    source: str
    details: Dict[str, Any]
    resolved: bool = False
```

#### 3. PrivacyManagerクラス構造
```python
class PrivacyManager:
    def __init__(self, config: BotConfig, bot: commands.Bot,
                 database_service: DatabaseService,
                 alert_manager: Optional[AlertManager] = None):
        # AlertManagerパターン踏襲

    # 個人情報検出エンジン
    async def detect_pii(self, text: str) -> List[PrivacyRule]

    # データマスキング機能
    async def apply_masking(self, text: str, privacy_level: PrivacyLevel) -> str

    # セキュリティ監査
    async def log_security_event(self, event: SecurityEvent) -> None

    # AlertManager連携
    async def trigger_privacy_alert(self, event: SecurityEvent) -> None
```

## 📊 BotConfig拡張設計

### 新規設定項目（AlertManagerパターン踏襲）
```python
# Privacy & Security settings
privacy_enabled: bool = Field(default=True, description="Enable privacy protection")
privacy_default_level: str = Field(default="medium", description="Default privacy level")
privacy_masking_type: str = Field(default="asterisk", description="Default masking type")
privacy_pii_detection: bool = Field(default=True, description="Enable PII detection")
privacy_api_key_detection: bool = Field(default=True, description="Enable API key detection")
privacy_audit_enabled: bool = Field(default=True, description="Enable security audit logging")
privacy_alert_integration: bool = Field(default=True, description="Integrate with AlertManager")
privacy_retention_days: int = Field(default=90, description="Privacy event retention days")
```

## 🗄️ データベーススキーマ設計

### 1. privacy_rules テーブル
```sql
CREATE TABLE IF NOT EXISTS privacy_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pattern TEXT NOT NULL,
    privacy_level TEXT NOT NULL,
    masking_type TEXT NOT NULL,
    enabled BOOLEAN DEFAULT 1,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. security_events テーブル
```sql
CREATE TABLE IF NOT EXISTS security_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    privacy_level TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,
    details TEXT, -- JSON形式
    resolved BOOLEAN DEFAULT 0,
    resolved_at TIMESTAMP
);
```

### 3. privacy_settings テーブル
```sql
CREATE TABLE IF NOT EXISTS privacy_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔍 個人情報検出パターン

### 組み込みパターン定義
```python
BUILTIN_PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone_jp": r'\b0\d{1,4}-\d{1,4}-\d{4}\b',
    "phone_us": r'\b\d{3}-\d{3}-\d{4}\b',
    "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
    "api_key": r'\b[A-Za-z0-9]{32,}\b',
    "jwt_token": r'\beyJ[A-Za-z0-9_/+\-=]+\b',
    "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
}
```

## 🎭 マスキング機能設計

### マスキングレベル別動作
```python
def apply_masking_by_level(text: str, privacy_level: PrivacyLevel) -> str:
    if privacy_level == PrivacyLevel.NONE:
        return text
    elif privacy_level == PrivacyLevel.LOW:
        return mask_partial(text, show_ratio=0.7)  # 70%表示
    elif privacy_level == PrivacyLevel.MEDIUM:
        return mask_partial(text, show_ratio=0.3)  # 30%表示
    elif privacy_level == PrivacyLevel.HIGH:
        return "***REDACTED***"
```

## 🚨 AlertManager連携設計

### プライバシー違反時の自動通知
```python
async def trigger_privacy_alert(self, event: SecurityEvent):
    if not self.alert_manager:
        return

    # AlertManagerのAlert形式に変換
    alert = Alert(
        id=f"privacy_{event.id}",
        title=f"Privacy Event: {event.event_type.value}",
        message=event.message,
        severity=self._map_privacy_to_alert_severity(event.privacy_level),
        timestamp=event.timestamp,
        source="PrivacyManager",
        metadata={"event_id": event.id, "event_type": event.event_type.value}
    )

    await self.alert_manager.send_alert(alert)
```

## 🧪 テスト戦略（AlertManagerパターン活用）

### テストクラス構造
```python
class TestPrivacyRule:         # AlertRuleテストパターン活用
class TestSecurityEvent:       # Alertテストパターン活用
class TestPrivacyManager:      # AlertManagerテストパターン活用
class TestPrivacyManagerIntegration:  # 統合テスト
```

### 予定テストケース数
**目標: 25-30テストケース**（AlertManager: 26ケースを参考）

1. **PrivacyRule/SecurityEvent**: 5ケース
2. **個人情報検出**: 8ケース
3. **マスキング機能**: 6ケース
4. **AlertManager連携**: 4ケース
5. **データベース操作**: 4ケース
6. **統合テスト**: 5ケース

## 📁 ファイル構成

```
src/nescordbot/services/privacy_manager.py    # メインサービス (約600-700行予定)
tests/services/test_privacy_manager.py        # テストスイート (約650-750行予定)
```

## 🔄 実装順序

### Phase 1: 基盤実装 (1日)
1. PrivacyManager基本クラス作成
2. Enum/dataclass定義
3. BotConfig拡張
4. データベーススキーマ作成

### Phase 2: 核心機能実装 (2日)
1. 個人情報検出エンジン
2. マスキング機能実装
3. セキュリティ監査システム

### Phase 3: 統合・テスト (1日)
1. AlertManager連携
2. ServiceContainer統合
3. 包括的テスト実装

## 🎯 成功指標

- **コードカバレッジ**: 80%以上
- **PII検出精度**: 95%以上（組み込みパターン）
- **マスキング精度**: 100%（設定レベル通り）
- **AlertManager連携**: 100%（イベント通知）
- **パフォーマンス**: テキスト処理 < 100ms

## 🔒 セキュリティ考慮事項

1. **ログ記録時の注意**: 検出した個人情報を平文でログに残さない
2. **メモリ管理**: 処理後の機密情報を適切にクリア
3. **設定セキュリティ**: パターン設定の不正変更防止
4. **監査証跡**: すべてのプライバシー操作を記録

---

## 📝 実装メモ

**AlertManagerとの主な差異点**:
- AlertManager: リアルタイム監視 → PrivacyManager: テキスト処理時点検出
- AlertManager: システムメトリクス → PrivacyManager: データ内容解析
- 共通点: 通知機能、設定管理、データベース統合

**開発効率化のポイント**:
- AlertManager実装時のServiceContainer統合パターン完全コピー
- BotConfig拡張パターンの再利用
- テスト構造の踏襲による品質確保
