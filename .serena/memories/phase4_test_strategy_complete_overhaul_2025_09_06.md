# Phase 4 テスト戦略 完全見直し計画 - 2025-09-06

## 🔍 現状分析と根本原因

### 構造的問題の特定
```
根本原因: ServiceContainerのファクトリーパターンとテストモックの根本的競合
├── 問題1: ファクトリーが先に登録され、シングルトン上書きが困難
├── 問題2: CI環境で実際のサービスインスタンスが作成される
├── 問題3: テスト環境とCI環境で異なる挙動
└── 問題4: 一貫性のないモック戦略による予測不可能な動作
```

### 失敗パターン分析
- **test_performance_under_load**: `Database not initialized` - 実際のTokenManagerが作成
- **test_knowledge_manager_chromadb_integration**: `Mock object has no attribute 'get_collection_info'` - 不完全なモック
- **その他**: detect_pii が空配列を返す - モック設定の競合状態

## 🎯 新戦略: Complete Test Isolation Pattern

### 設計原則
1. **完全分離**: テスト環境で実際のサービスを一切作成しない
2. **事前確定**: すべてのモックを事前に登録し、動的生成を排除
3. **環境無依存**: CI/ローカル環境で同一の動作を保証
4. **レイヤー分離**: Unit/Integration/E2Eテストの明確な分離

## 🏗️ アーキテクチャ設計

### Phase 1: テスト専用インフラ構築

#### 1.1 TestServiceContainer
```python
class TestServiceContainer(ServiceContainer):
    """テスト専用ServiceContainer - 実サービス作成を完全に阻止"""

    def __init__(self, config: BotConfig):
        super().__init__(config)
        self._test_mode = True
        self._mock_registry: Dict[Type, Any] = {}
        self._factory_blocked = True

    def register_factory(self, service_type, factory):
        """テストモードではファクトリー登録を無視"""
        if self._test_mode:
            logger.debug(f"Blocked factory registration for {service_type.__name__}")
            return
        super().register_factory(service_type, factory)

    def get_service(self, service_type: Type[T]) -> T:
        """モックレジストリから取得、存在しない場合はエラー"""
        if service_type in self._mock_registry:
            return self._mock_registry[service_type]
        raise TestConfigurationError(f"Mock not registered for {service_type.__name__}")
```

#### 1.2 TestBotFactory
```python
class TestBotFactory:
    @staticmethod
    async def create_isolated_bot(config: BotConfig) -> NescordBot:
        """完全に分離されたテスト専用Bot"""

        # Discord関連を完全にモック
        with patch("discord.Client.login"), patch("discord.Client.connect"):
            bot = NescordBot()
            bot.config = config

            # テスト専用ServiceContainerで置換
            bot.service_container = TestServiceContainer(config)

            # データベースサービスも完全モック
            bot.database_service = create_mock_database_service()

            # 全サービスモックの事前登録
            await TestBotFactory._register_complete_mock_set(bot)

            return bot
```

### Phase 2: 統一モック戦略

#### 2.1 ServiceMockRegistry - 中央集権的モック管理
```python
class ServiceMockRegistry:
    """全サービスモックの一元管理と生成"""

    @staticmethod
    def create_complete_set(config: BotConfig, db_service) -> Dict[Type, Any]:
        """完全なモックセットを作成"""

        registry = {}

        # TokenManager - 完全API互換
        registry[TokenManager] = TokenManagerMock.create_full_mock(config, db_service)

        # PrivacyManager - PII検出モック含む
        registry[PrivacyManager] = PrivacyManagerMock.create_full_mock(config, db_service)

        # KnowledgeManager - ノート管理モック
        registry[KnowledgeManager] = KnowledgeManagerMock.create_full_mock(config, db_service)

        # 他のサービス...

        # 依存関係の設定
        ServiceMockRegistry._setup_service_dependencies(registry)

        return registry
```

#### 2.2 Smart Mock Classes - 完全API互換モック
```python
class TokenManagerMock:
    @classmethod
    def create_full_mock(cls, config: BotConfig, db_service) -> AsyncMock:
        """完全にAPI互換なTokenManagerモック"""

        mock = AsyncMock(spec=TokenManager)
        mock._initialized = True
        mock.config = config
        mock.db = db_service

        # 全パブリックメソッドの実装
        cls._setup_record_usage(mock)
        cls._setup_check_limits(mock)
        cls._setup_get_usage_history(mock)
        cls._setup_get_monthly_usage(mock)
        cls._setup_health_check(mock)
        cls._setup_calculate_cost(mock)

        return mock

    @staticmethod
    def _setup_record_usage(mock):
        """record_usage のリアルな動作模擬"""
        async def mock_record_usage(provider, model, input_tokens=0, output_tokens=0, **kwargs):
            # バリデーション模擬
            if not provider or not model:
                raise ValueError("Provider and model are required")
            # 成功を模擬
            return None

        mock.record_usage.side_effect = mock_record_usage
```

### Phase 3: テスト分類とレイヤー化

#### 3.1 テストピラミッド実装
```
E2E Tests (Level 3) - 最小限、実環境
├── 実際のDB + 実際のAPI
├── 重要ワークフローのみ
├── @pytest.mark.e2e
└── CI では条件付き実行

Integration Tests (Level 2) - 中心、完全モック
├── TestServiceContainer使用
├── サービス間連携テスト
├── @pytest.mark.integration
└── CI でメイン実行

Unit Tests (Level 1) - 最大量、高速
├── 個別サービス単体テスト
├── @pytest.mark.unit
└── 即座に実行
```

#### 3.2 テスト設定の階層化
```python
# conftest.py
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """テスト環境のグローバル設定"""
    os.environ["NESCORDBOT_TEST_MODE"] = "true"
    os.environ["NESCORDBOT_CI_MODE"] = str(os.getenv("CI", "false").lower() == "true")
    yield
    # クリーンアップ

@pytest.fixture
async def isolated_bot(test_config):
    """完全分離されたテスト用Bot - デフォルトfixture"""
    bot = await TestBotFactory.create_isolated_bot(test_config)
    yield bot
    await bot.service_container.shutdown_services()

@pytest.fixture
async def performance_bot(test_config):
    """パフォーマンステスト用の特別設定Bot"""
    bot = await TestBotFactory.create_isolated_bot(test_config)
    # パフォーマンステスト用の特別モック設定
    PerformanceMockConfigurator.configure(bot)
    yield bot
    await bot.service_container.shutdown_services()
```

## 🚀 実装計画

### ステップ1: 基盤構築 (Priority: 最高)
```
1. tests/infrastructure/test_service_container.py
2. tests/infrastructure/test_bot_factory.py
3. tests/mocks/service_mock_registry.py
4. tests/mocks/base_mock.py

完了基準: TestServiceContainerで実サービスが作成されないこと
推定時間: 2-3時間
```

### ステップ2: Smart Mock実装 (Priority: 高)
```
1. tests/mocks/token_manager_mock.py
2. tests/mocks/privacy_manager_mock.py
3. tests/mocks/knowledge_manager_mock.py
4. tests/mocks/alert_manager_mock.py
5. 他の全サービスモック

完了基準: 全サービスのAPI互換性100%達成
推定時間: 4-5時間
```

### ステップ3: テスト移行 (Priority: 中)
```
1. test_phase4_essential.py の完全書き換え
2. test_phase4_integration.py の完全書き換え
3. 新しいテストマーカーの適用
4. conftest.py の更新

完了基準: 全Integration TestがCI環境で安定動作
推定時間: 3-4時間
```

### ステップ4: CI最適化 (Priority: 中)
```
1. .github/workflows/ci.yml の更新
2. pytest.ini の設定追加
3. パフォーマンステストの分離
4. 並列実行の最適化

完了基準: CI実行時間30%短縮、安定性99%達成
推定時間: 1-2時間
```

## 📊 期待される効果

### 品質向上
- **安定性**: CI環境で99%以上の成功率
- **予測可能性**: 環境による動作差異の完全排除
- **保守性**: 一元化されたモック管理によるメンテナンス効率向上

### 開発効率向上
- **実行速度**: Integration Test実行時間50%短縮
- **並列性**: 完全な分離によるテスト並列実行
- **デバッグ性**: 明確な失敗原因の特定

### 技術負債削減
- **一貫性**: 統一されたモック戦略
- **拡張性**: 新サービス追加時の標準パターン
- **文書化**: 自己文書化されたテストアーキテクチャ

## 🎯 成功メトリクス

### 短期目標 (1週間以内)
- [ ] CI環境でのPhase4テスト成功率: 95%以上
- [ ] テスト実行時間: 50%短縮
- [ ] テスト分離度: 100% (実サービス作成ゼロ)

### 中期目標 (2週間以内)
- [ ] 新サービステストの標準化完了
- [ ] E2Eテストの選択実行体制確立
- [ ] 開発者向けテストガイド作成

### 長期目標 (1ヶ月以内)
- [ ] テストカバレッジ80%維持
- [ ] 全開発者がテスト戦略を理解・活用
- [ ] 継続的な品質改善サイクル確立

## 📝 参照ドキュメント

- ServiceContainer実装: `src/nescordbot/services/service_container.py`
- 現在のテスト: `tests/integration/test_phase4_*.py`
- CI設定: `.github/workflows/ci.yml`
- 問題Issue: #163

---

**記録日時**: 2025-09-06
**戦略策定者**: Claude Code Assistant
**レビュー予定**: 実装完了後
**更新予定**: 実装結果に基づく戦略修正
