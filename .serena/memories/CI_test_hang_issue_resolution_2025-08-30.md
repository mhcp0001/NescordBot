# CI テストハング問題の調査と解決 (2025-08-30)

## 問題の概要
PR #141 (feature/108-gemini-audio-migration) のCIテストが15分でタイムアウトし、pytestの実行中にハングする問題が発生。

## 症状
- **テスト数**: 629個のテスト中624個が完了後、残り5個でハング
- **タイムアウト**: ジョブ全体が15分でタイムアウト
- **最後の成功テスト**: `test_whisper.py::TestWhisperTranscriptionService::test_transcribe_general_error`
- **警告メッセージ**: `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`

## 根本原因の特定

### 1. AsyncMock/MagicMock の不適切な使用
**場所**: `tests/test_batch_processor.py`
- `queue.set_git_service()` は同期メソッドだが、AsyncMockでモックされていた
- 71行目で `self.queue.set_git_service(self.git_operations)` 呼び出し時に警告発生

### 2. 外部API接続によるハング
**場所**: CI環境での `GEMINI_API_KEY` 設定
- `${{ secrets.GEMINI_API_KEY }}` が実際のAPIキーを使用
- テスト実行時に外部Gemini APIへの接続でハング

### 3. pytest並列実行の問題
- pytest-xdist による並列実行が pytest-timeout と干渉する可能性

## 実施した修正

### 1. test_batch_processor.py の修正
```python
# 修正前
mock_queue = AsyncMock()
# set_git_service メソッドも AsyncMock になってしまう

# 修正後
mock_queue = AsyncMock()
mock_queue.set_git_service = MagicMock()  # 同期メソッドは MagicMock を使用
```

### 2. pytest-timeout プラグインの追加
```toml
# pyproject.toml
pytest-timeout = "^2.1.0"
```

### 3. CI設定の改善
```yaml
# .github/workflows/ci.yml
run: |
  poetry run pytest tests/ \
    -vvv \              # 最詳細ログ出力
    --capture=no \      # リアルタイム出力
    -n 0 \              # 並列実行を無効化
    --timeout=600 \     # 10分の個別テストタイムアウト
    --timeout-method=thread \
    -p faulthandler     # デッドロック検出
```

### 4. GEMINI_API_KEY の修正
```yaml
# 修正前
GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}

# 修正後  
GEMINI_API_KEY: test-gemini-key  # ダミー値に固定
```

## デバッグワークフローの作成
`.github/workflows/debug-hanging-tests.yml` を作成し、以下を実装：

1. **identify-hanging-tests**: すべてのテストを収集して最後の10個を表示
2. **test-individual-files**: 疑わしい5つのテストファイルを個別実行
   - test_batch_processor.py
   - test_persistent_queue.py
   - test_git_operations.py
   - test_github_auth.py
   - test_obsidian_github_integration.py
3. **find-last-5-tests**: 実行順序で最後のテストを特定

### デバッグ結果
- 個別実行ではすべてのテストが**成功**
- 629個中626個のテストが収集可能（whisper除外時）
- 問題は特定の3個のテストにある可能性

## Gemini との協力による分析

Gemini からの助言：
1. **並列実行の無効化** (`-n 0`) - pytest-xdist と pytest-timeout の干渉を排除
2. **詳細ログ出力** (`-vvv --capture=no`) - ハング箇所のリアルタイム特定
3. **個別テストタイムアウト** - ジョブ全体ではなく個別テストにタイムアウト設定
4. **環境変数の問題** - 外部API接続がタイムアウトの原因になる可能性

## 重要な発見

### ERRORログの正しい理解
ログに表示される以下のようなERRORは**正常なテストの一部**：
```
test_verify_migration_integrity
ERROR | Migration 1 checksum mismatch: expected ceaebca51156d19a7ecce325414acb52, got invalid
PASSED
```
これらは「エラーを検出できるか」を確認するテストで、ERRORが出ることが期待される動作。

### テスト実行状況
- **624個のテスト**: 実際に実行され成功
- **629個のテスト**: 元々収集された総数
- **5個の差分**: ハングの原因となったテスト

## 最終的な解決策

1. **AsyncMock問題の修正**: 同期メソッドには MagicMock を使用
2. **外部API接続の防止**: GEMINI_API_KEY をダミー値に固定
3. **デバッグ情報の強化**: 詳細ログとタイムアウト設定
4. **並列実行の無効化**: テスト間の競合を排除

## コミット履歴
1. `c88f45a`: pytest デバッグオプション追加
2. `4fecf65`: pytest-timeout 依存関係追加
3. `f3c65fc`: 詳細デバッグ用設定（-vvv, --capture=no, -n 0）
4. `a812b41`: batch_processor AsyncMock 警告修正
5. `0c547c3`: デバッグワークフロー追加
6. `2839e74`: GEMINI_API_KEY をダミー値に固定

## 今後の推奨事項

1. **環境変数管理**: テスト用環境変数は常にダミー値を使用
2. **モック設計**: 同期/非同期メソッドを明確に区別してモック
3. **CI タイムアウト**: ジョブ全体と個別テストの両方にタイムアウト設定
4. **デバッグツール**: 問題発生時用のデバッグワークフローを維持

## 関連ファイル
- `.github/workflows/ci.yml`: メインのCI設定
- `.github/workflows/debug-hanging-tests.yml`: デバッグ用ワークフロー
- `tests/test_batch_processor.py`: AsyncMock問題の修正箇所
- `pyproject.toml`: pytest-timeout 追加

## 問題解決のタイムライン
- 問題発見: CI実行 #17339144576 でハング確認
- 調査開始: ログ分析により624/629テスト完了を確認
- 原因特定: AsyncMock警告と外部API接続を特定
- 修正適用: 段階的に4つの修正を実施
- 解決確認: 最終CI実行待ち

この問題は、モックの適切な使用と外部依存の管理の重要性を示す良い事例となった。