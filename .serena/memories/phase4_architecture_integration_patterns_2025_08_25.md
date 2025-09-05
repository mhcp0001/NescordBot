# Phase 4アーキテクチャ統合パターン記録 (2025-08-25)

## アーキテクチャ統合概要

Phase 4 PKM機能開発において、ServiceContainer依存性注入、BotConfig拡張、EmbeddingService実装を通じて確立したアーキテクチャパターンと統合手法。

## 依存性注入アーキテクチャ

### ServiceContainer設計パターン

**実装**: Issue #95 ServiceContainer
```python
class ServiceContainer:
    def register_service(self, service_type: Type[T], instance: T) -> None
    def register_singleton(self, service_type: Type[T], instance: T) -> None
    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None
    def get_service(self, service_type: Type[T]) -> T
```

**型安全性確保**:
```python
T = TypeVar("T")

# 使用例
container = get_service_container()
embedding_service = container.get_service(EmbeddingService)  # Type[EmbeddingService]
```

### ファクトリーパターン統合

**EmbeddingService統合例**:
```python
def _init_service_container(self) -> None:
    self.service_container = create_service_container(self.config)

    # ファクトリー登録
    def create_embedding_service() -> EmbeddingService:
        return EmbeddingService(self.config)

    self.service_container.register_factory(EmbeddingService, create_embedding_service)
```

**利点**:
- 遅延初期化による起動時間短縮
- 設定依存の動的サービス生成
- テスト時のモック注入容易性

## 設定管理統合パターン

### BotConfig Phase 4拡張 (Issue #96)

**階層的設定構造**:
```python
class BotConfig(BaseModel):
    # Phase 4: Gemini API settings
    gemini_api_key: Optional[str] = Field(default=None)
    gemini_monthly_limit: int = Field(default=50000)
    gemini_requests_per_minute: int = Field(default=15)

    # Phase 4: ChromaDB settings
    chromadb_persist_directory: str = Field(default="data/chromadb")
    chromadb_collection_name: str = Field(default="nescord_knowledge")
    chromadb_distance_metric: str = Field(default="cosine")

    # Phase 4: PKM settings
    embedding_dimension: int = Field(default=768)
    ai_api_mode: str = Field(default="openai")  # openai/gemini/hybrid
    enable_api_fallback: bool = Field(default=True)
```

### 相互依存性バリデーション

**複雑な設定依存関係の処理**:
```python
@model_validator(mode='after')
def validate_dependencies(self):
    # PKM有効時のGemini API key必須チェック
    if self.pkm_enabled:
        if self.ai_api_mode in ["gemini", "hybrid"] and not self.gemini_api_key:
            raise ValueError("Gemini API key is required when PKM is enabled")

    # ChromaDB persist directory存在確認
    if self.pkm_enabled:
        persist_path = Path(self.chromadb_persist_directory)
        if persist_path.exists() and not persist_path.is_dir():
            raise ValueError(f"ChromaDB persist directory is not a directory")
```

## サービス統合レイヤーパターン

### bot.py統合ハブ設計

**統合ポイント集約**:
```python
class NescordBot(commands.Bot):
    def __init__(self):
        # 設定管理
        self.config = get_config_manager().config

        # 従来サービス初期化
        self._init_legacy_services()

        # ObsidianGitHub統合サービス
        self._init_obsidian_services()

        # Phase 4サービスコンテナ
        self._init_service_container()
```

**段階的初期化**:
```python
async def setup_hook(self) -> None:
    # 同期初期化完了サービス
    await self.database_service.initialize()

    # 非同期初期化サービス (ObsidianGitHub)
    await self._init_obsidian_services_async()

    # ServiceContainer管理サービス (Phase 4)
    # ファクトリー登録済みのため、遅延初期化で対応
```

## エラーハンドリング階層

### 例外階層設計

**EmbeddingService例外階層**:
```python
class EmbeddingServiceError(Exception):
    """Base exception for EmbeddingService."""
    pass

class EmbeddingAPIError(EmbeddingServiceError):
    """API-related errors."""
    pass

class EmbeddingRateLimitError(EmbeddingServiceError):
    """Rate limit exceeded."""
    pass
```

**階層的エラー処理**:
```python
try:
    result = await embedding_service.generate_embedding(text)
except EmbeddingRateLimitError as e:
    # レート制限特化処理
    await asyncio.sleep(60)
    retry_result = await embedding_service.generate_embedding(text)
except EmbeddingAPIError as e:
    # API エラー処理
    logger.error(f"Embedding API error: {e}")
    raise
except EmbeddingServiceError as e:
    # 一般的なサービスエラー処理
    logger.warning(f"Embedding service error: {e}")
    return None
```

## 非同期処理統合パターン

### 混在環境での非同期処理

**Discord.py + 独自非同期サービス**:
```python
# ServiceContainer内での非同期サービス管理
async def initialize_services(self) -> None:
    """Initialize all registered services that support async initialization."""
    for service_type, instance in self._services.items():
        if hasattr(instance, 'initialize') and callable(instance.initialize):
            try:
                await instance.initialize()
            except Exception as e:
                raise ServiceInitializationError(service_type, e)
```

**EmbeddingService非同期設計**:
```python
# tenacityによるリトライ + 非同期
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((EmbeddingAPIError,))
)
async def _generate_embedding_api(self, text: str) -> List[float]:
    # Gemini API呼び出し (同期) を非同期コンテキストで実行
    response = genai.embed_content(...)
    return response['embedding']
```

## テスト統合戦略

### モック統合パターン

**ServiceContainer テスト統合**:
```python
@pytest.fixture
def mock_service_container():
    from nescordbot.services import reset_service_container, create_service_container

    # テスト用クリーンスレート
    reset_service_container()

    # テスト用設定
    test_config = create_test_config()
    container = create_service_container(test_config)

    yield container

    # クリーンアップ
    reset_service_container()
```

**EmbeddingService モックパターン**:
```python
def test_embedding_service_integration(mock_service_container):
    # モックサービス注入
    mock_embedding_service = Mock(spec=EmbeddingService)
    mock_service_container.register_service(EmbeddingService, mock_embedding_service)

    # 実際の統合テスト
    service = mock_service_container.get_service(EmbeddingService)
    assert service is mock_embedding_service
```

## Phase統合ブランチ戦略

### ブランチ統合アーキテクチャ

**統合フロー**:
```
main
├── feature/phase4                    # Phase統合ブランチ
    ├── feature/95-service-container  # ServiceContainer
    ├── feature/96-botconfig-phase4   # BotConfig拡張
    ├── feature/99-embedding-gemini   # EmbeddingService
    └── feature/97-database-schema    # 次期統合対象
```

**統合利点**:
- 複数サービスの相互作用テスト
- 段階的品質保証
- CI負荷分散

### 統合テストパターン

**ServiceContainer + EmbeddingService統合テスト**:
```python
async def test_integration():
    config_manager = get_config_manager()
    config = config_manager.config

    # ServiceContainer作成
    container = create_service_container(config)

    # EmbeddingServiceファクトリー登録
    def create_embedding_service() -> EmbeddingService:
        return EmbeddingService(config)

    container.register_factory(EmbeddingService, create_embedding_service)

    # 統合動作確認
    embedding_service = container.get_service(EmbeddingService)
    health = await embedding_service.health_check()
    assert health['service'] == 'EmbeddingService'
```

## パフォーマンス最適化パターン

### 遅延初期化最適化

**重いサービスの遅延初期化**:
```python
# EmbeddingService: 初回使用時までGemini API接続遅延
def _setup_gemini_client(self) -> None:
    try:
        if not self.config.gemini_api_key:
            self._gemini_available = False
            return

        genai.configure(api_key=self.config.gemini_api_key)
        self._gemini_available = True
    except Exception as e:
        self._gemini_available = False
```

### キャッシュ統合パターン

**多層キャッシュ戦略**:
```python
# EmbeddingService: MD5ハッシュ + LRUクリーンアップ
def _get_cached_embedding(self, text: str) -> Optional[EmbeddingResult]:
    text_hash = self._get_text_hash(text)  # MD5
    if text_hash in self._cache:
        entry = self._cache[text_hash]
        entry.access_count += 1  # LRU更新
        return EmbeddingResult(..., cached=True)
```

## 今後の統合展望

### 次期サービス統合予定

**データベース層統合**:
- Issue #97: データベーススキーマ拡張
- knowledge_notes, note_links, token_usage テーブル
- ServiceContainer + DatabaseService統合

**ベクトル検索層統合**:
- Issue #100: ChromaDBService
- EmbeddingService → ChromaDBService データフロー
- ベクトル類似検索基盤

**知識管理層統合**:
- Issue #103: KnowledgeManager
- EmbeddingService + ChromaDBService統合活用
- PKM機能中核ロジック

### アーキテクチャ発展予想

**最終統合形態**:
```
ServiceContainer
├── EmbeddingService (✅)
├── ChromaDBService (→ Issue #100)
├── TokenManager (→ Issue #98)
├── DatabaseService (既存拡張)
└── KnowledgeManager (→ Issue #103)
    └── PKMCog (→ Issue #105)
```

このアーキテクチャパターンにより、複雑なPhase 4機能群の統合を段階的かつ安全に実現する基盤が確立された。
