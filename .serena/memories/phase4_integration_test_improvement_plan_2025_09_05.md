# Phase 4統合テスト改善計画 - 詳細実装ガイド
**策定日**: 2025-09-05
**目的**: スモークテストから実用レベルの品質保証への段階的改善

## 📋 全体計画概要

### 現状分析
- **現在**: スモークテスト14/14 PASS（基本動作のみ確認）
- **問題**: 実際の機能動作・サービス連携が未検証
- **リスク**: PII検出精度、データ永続性、サービス間通信が保証されていない

### 目標設定
- **短期**: 主要機能の実動作確認（品質レベル: 最小限→実用可能）
- **中期**: サービス連携の動作確認（品質レベル: 実用可能→安定）
- **長期**: エンドツーエンドフローの確認（品質レベル: 安定→本番準備）

## 🎯 Phase 1: 重要機能の実動作テスト追加（1-2日）

### 1.1 PrivacyManager実際のPII検出テスト

#### 実装内容
```python
# tests/integration/test_phase4_functional.py
class TestPhase4FunctionalIntegration:
    async def test_privacy_manager_real_pii_detection(self, functional_bot):
        """PrivacyManagerが実際にPII検出とマスキングを行えるかテスト"""

        # テストケース
        test_cases = [
            {
                "text": "私のメールは john.doe@example.com です",
                "expected_detection": "email",
                "should_detect": True
            },
            {
                "text": "電話番号は 090-1234-5678 です",
                "expected_detection": "phone",
                "should_detect": True
            },
            {
                "text": "普通のテキストです",
                "expected_detection": None,
                "should_detect": False
            }
        ]
```

#### 検証ポイント
1. **実際のPIIルール読み込み**: ビルトインルールが正しく動作
2. **検出精度**: 実際のPIIパターンを正確に検出
3. **マスキング機能**: 検出されたPIIが適切にマスキング
4. **パフォーマンス**: 大量テキストでもタイムアウトしない

### 1.2 AlertManager通知機能テスト

#### 実装内容
```python
async def test_alert_manager_notification_functionality(self, functional_bot):
    """AlertManagerが実際に通知処理を行えるかテスト"""

    # Discordクライアントをモック
    with patch('discord.TextChannel.send') as mock_send:
        alert_manager = functional_bot.service_container.get_service(AlertManager)

        # 実際のアラート作成とトリガー
        test_alert = Alert(...)
        await alert_manager._trigger_alert(test_alert)

        # 通知が送信されたか確認
        mock_send.assert_called_once()
```

#### 検証ポイント
1. **アラート生成**: Alert オブジェクトの正しい作成
2. **Discord通知**: モックを使った通知送信確認
3. **データベース保存**: アラート履歴の永続化
4. **重複制御**: 同一アラートの重複防止

## 🔗 Phase 2: サービス連携テスト（2-3日）

### 2.1 Privacy→Alert連携テスト

#### 実装内容
```python
async def test_privacy_alert_integration(self, functional_bot):
    """PII検出時のアラート連携テスト"""

    privacy_manager = functional_bot.service_container.get_service(PrivacyManager)
    alert_manager = functional_bot.service_container.get_service(AlertManager)

    # PII含むテキストを処理
    pii_text = "秘密情報: john.doe@example.com"

    with patch.object(alert_manager, '_trigger_alert') as mock_alert:
        # PII検出とマスキング
        detected = await privacy_manager.detect_pii(pii_text)
        masked = await privacy_manager.apply_masking(pii_text, PrivacyLevel.HIGH)

        # アラートが発火されたか確認
        mock_alert.assert_called()

        # 連携データの整合性確認
        alert_call = mock_alert.call_args[0][0]
        assert "PII detected" in alert_call.message
```

### 2.2 Token→Fallback連携テスト

#### 実装内容
```python
async def test_token_fallback_integration(self, functional_bot):
    """API制限時のフォールバック動作テスト"""

    token_manager = functional_bot.service_container.get_service(TokenManager)
    fallback_manager = functional_bot.service_container.get_service(FallbackManager)

    # APIトークン制限をシミュレート
    await token_manager.track_usage("test_api", "embedding", 1000000)  # 大量使用

    # 制限チェック
    is_limited = await token_manager.check_rate_limit("test_api", "embedding")

    if is_limited:
        # フォールバック機能の動作確認
        fallback_result = await fallback_manager.get_fallback_service("embedding")
        assert fallback_result is not None
```

## 🔄 Phase 3: 簡易エンドツーエンドテスト（3-4日）

### 3.1 音声→PKMフローテスト

#### 実装内容
```python
async def test_voice_to_pkm_workflow(self, functional_bot):
    """音声ファイルからPKMノート作成までの完全フロー"""

    # モック音声データ
    mock_audio_content = b"fake_audio_data"

    with patch('src.nescordbot.services.voice_service.transcribe_audio') as mock_transcribe:
        mock_transcribe.return_value = "これはテスト音声の内容です"

        # 1. 音声アップロード（モック）
        # 2. 文字起こし
        transcription = await voice_service.process_audio(mock_audio_content)

        # 3. PKMサービスでノート作成
        knowledge_manager = functional_bot.service_container.get_service(KnowledgeManager)
        note_id = await knowledge_manager.create_note(
            title="Test Note",
            content=transcription,
            tags=["audio", "test"]
        )

        # 4. 検索可能性確認
        search_engine = functional_bot.service_container.get_service(SearchEngine)
        search_results = await search_engine.search("テスト音声")

        # 検証
        assert note_id is not None
        assert len(search_results) > 0
        assert any(result.note_id == note_id for result in search_results)
```

### 3.2 バックアップ・復元フローテスト

#### 実装内容
```python
async def test_backup_restore_workflow(self, functional_bot):
    """データバックアップと復元の整合性テスト"""

    backup_manager = functional_bot.service_container.get_service(BackupManager)
    knowledge_manager = functional_bot.service_container.get_service(KnowledgeManager)

    # テストデータ作成
    original_note_id = await knowledge_manager.create_note(
        title="Backup Test Note",
        content="This is test content for backup",
        tags=["backup", "test"]
    )

    # バックアップ作成
    backup_path = await backup_manager.create_backup()
    assert backup_path.exists()

    # データ削除（復元テスト用）
    await knowledge_manager.delete_note(original_note_id)

    # 復元実行
    await backup_manager.restore_backup(backup_path)

    # データ整合性確認
    restored_note = await knowledge_manager.get_note(original_note_id)
    assert restored_note is not None
    assert restored_note.title == "Backup Test Note"
```

## 📁 ファイル構成

### 新規作成ファイル
```
tests/integration/
├── test_phase4_functional.py      # Phase 1実装
├── test_phase4_service_integration.py  # Phase 2実装
└── test_phase4_end_to_end.py      # Phase 3実装
```

### 既存ファイル拡張
```
tests/integration/test_phase4_smoke.py  # 成功パターンを参考に拡張
```

## 🎛️ 実装戦略

### 段階的実装
1. **Phase 1優先**: 単一サービスの実機能確認
2. **成功ベース**: 既存のスモークテスト成功パターンを活用
3. **モック活用**: 外部依存を適切にモック化
4. **エラーハンドリング**: try-except-skipパターンで堅牢性確保

### 品質指標
- **Phase 1完了**: 実機能テスト 4/4 PASS
- **Phase 2完了**: サービス連携テスト 2/2 PASS
- **Phase 3完了**: E2Eテスト 2/2 PASS

### 成功の定義
各Phaseで「実際に期待された機能が動作する」ことを確認し、スモークテストレベルから実用レベルの品質保証に段階的に引き上げる。

## 📊 期待される改善効果

### テスト信頼性
- **現在**: 基本動作のみ確認（スモークレベル）
- **Phase 1完了後**: 主要機能の実動作確認（実用レベル）
- **Phase 2完了後**: サービス連携の動作確認（安定レベル）
- **Phase 3完了後**: エンドツーエンドフローの確認（本番準備レベル）

### 開発効率
- 問題の早期発見とデバッグ効率化
- リファクタリング時の安全性向上
- 新機能追加時の影響範囲把握

この計画により、Phase 4の品質保証を段階的かつ確実に改善していきます。
