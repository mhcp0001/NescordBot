# Async Exception Handling & Testing Lessons - 2025-08-28

## 🚨 重要な発見: async context manager例外抑制問題

### 問題の本質
- **async with** コンテキストマネージャー内で例外を発生させると、`__aexit__`メソッドにより例外が抑制される場合がある
- この問題により、テストで期待している例外が実際には発生せず、代わりに空の結果やデフォルト値が返される
- 結果的に「テストを通すための修正」（技術的負債）を生み出す危険性

### 具体的事例
```python
# ❌ 問題のあるコード
async with self.db.get_connection() as conn:
    cursor = await conn.execute("SELECT ... WHERE id = ?", (note_id,))
    source_row = await cursor.fetchone()

    if not source_row:
        raise LinkSuggestionError(f"Note {note_id} not found")  # 例外が抑制される！

# ✅ 修正後のコード
async with self.db.get_connection() as conn:
    cursor = await conn.execute("SELECT ... WHERE id = ?", (note_id,))
    source_row = await cursor.fetchone()

# 例外チェックをコンテキストマネージャー外部に移動
if not source_row:
    raise LinkSuggestionError(f"Note {note_id} not found")  # 正常に例外発生
```

## 🧪 テスト設計の重要な教訓

### 1. テスト期待値の妥当性検証
- **問題**: 初期修正では例外期待テストを空リスト期待に変更した
- **影響**: これにより本来の例外処理セマンティクスが失われる
- **解決**: 元のテスト期待値（例外）が正しいことを再確認し、実装側を修正

```python
# ❌ 間違った「修正」
# assert suggestions == []  # 空リストを期待（エラーを隠蔽）

# ✅ 正しいテスト
with pytest.raises(LinkSuggestionError, match="Note test-id not found"):
    await suggestor.suggest_links_for_note("test-id")
```

### 2. UnboundLocalError vs 例外処理の区別
- **UnboundLocalError**: 変数が初期化前に参照される問題
- **例外処理**: ビジネスロジックでの適切なエラーハンドリング
- **重要**: 前者を修正するために後者を破綻させてはいけない

### 3. モック設定の精密性
```python
# 正確なモック設定が重要
mock_cursor.fetchone = AsyncMock(return_value=None)  # 「見つからない」状況
mock_cursor.fetchall = AsyncMock(return_value=[])    # 「候補なし」状況
```

## 🔍 デバッグ手法の有効性

### 1. 段階的問題切り分け
1. デバッグprint文で例外発生箇所を特定
2. async context managerの動作を詳細分析
3. 例外の伝播経路を追跡
4. 最終的に根本原因（例外抑制）を発見

### 2. Claude-Gemini協力パターン
- **Claude**: 徹底的なコード分析とデバッグ
- **Gemini**: 多角的視点での問題検証
- **証拠ベース判断**: ログとテスト結果に基づく確実な修正

## 🏗️ アーキテクチャ設計の学び

### 1. 例外処理の一貫性
- サービス層での例外は適切に伝播させる
- ビジネスロジック例外（LinkSuggestionError）とシステム例外を明確に区別
- 例外の再ラップ時も元の意図を保持

### 2. テスト駆動開発の価値
- 正しいテストがあることで、実装の問題を早期発見
- テストの変更は慎重に行い、ビジネス要件との整合性を確認
- 「テストを通すだけの修正」は技術的負債の温床

## 🚀 品質保証プロセス

### 1. 段階的修正アプローチ
1. 問題の完全な理解
2. 最小限の修正による根本解決
3. デバッグコードの削除
4. 全テストでの検証
5. コミット前の品質チェック

### 2. CI/CDでの検証
- pre-commitフックでの自動品質チェック
- 複数Python版での並列テスト実行
- セキュリティ・統合テストの包括実行

## 📋 今後の開発指針

### 1. async処理での注意事項
- コンテキストマネージャー内での例外処理は慎重に設計
- 例外の伝播経路を明確に理解
- デバッグ時は例外抑制の可能性を常に考慮

### 2. テスト品質の維持
- テスト変更時は必ずビジネス要件に立ち戻る
- 「通すだけの修正」を避け、根本原因を追求
- モック設定は実際のデータフローを正確に模倣

### 3. 技術的負債の予防
- 一時的な修正と恒久的な解決を明確に区別
- コードレビューで例外処理の妥当性を重点チェック
- 定期的な例外処理パターンの見直し

---

**記録日**: 2025-08-28
**対象Issue**: #107 ノートリンク機能実装
**影響範囲**: LinkSuggestor, LinkValidator, 関連テストスイート
**学習価値**: ★★★★★ (最重要レベル)
