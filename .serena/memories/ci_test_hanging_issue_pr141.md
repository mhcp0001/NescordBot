# CI Test Hanging Issue - PR #141 (Gemini Audio API Migration)

## 問題概要
PR #141において、pytestがテスト実行中にハング（無限に停止）する問題が発生。CI/CDパイプラインがタイムアウトで失敗。

## 症状
- **テスト進捗**: 629テスト中624テストが成功、残り5テストでハング
- **最後の成功テスト**: `test_whisper.py::TestWhisperTranscriptionService::test_transcribe_general_error`
- **タイムアウト**: 15分でGitHub Actionsがタイムアウト
- **影響バージョン**: Python 3.11と3.12の両方で発生

## 試行した修正（すべて効果なし）

### 1. AsyncMock/MagicMock修正
**問題**: `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`
**修正内容**:
- `test_batch_processor.py`: `set_git_service`を`AsyncMock`から`MagicMock`に変更
- `test_voice.py`: `TranscriptionService`の`is_available`プロパティを適切にモック
- `test_obsidian_github_integration.py`: `NoteProcessingService`のモック修正

### 2. pytest設定の改善
**追加したオプション**:
```bash
-vvv                    # 詳細ログ出力
--capture=no           # stdout/stderrをキャプチャしない
-n 0                   # 並列実行を無効化
--timeout=600          # 個別テストタイムアウト（10分）
--timeout-method=thread # スレッドベースのタイムアウト
-p faulthandler        # Pythonのfaulthandlerを有効化
```

### 3. 外部API接続の防止
**環境変数の変更**:
```yaml
GEMINI_API_KEY: test-gemini-key  # 実際のAPIキーからダミー値に変更
```
**目的**: 外部APIへの接続試行によるハングを防ぐ

### 4. デバッグワークフローの作成
**`.github/workflows/debug-hanging-tests.yml`**を作成し、個別テスト実行を試行
**結果**: すべてのテストファイルが個別実行では成功（重要な発見）

## 重要な発見

### 個別実行vs一括実行の違い
- **個別実行**: すべてのテストファイルが成功
- **一括実行**: 624テスト後にハング
- **示唆**: テスト間の相互作用または累積的なリソース問題の可能性

### ハングが発生する箇所
```
test_whisper.py::TestWhisperTranscriptionService::test_transcribe_general_error PASSED
[ここでハング - 次のテストに進まない]
```

### エラーログの意図的な出力
CI中に表示される`ERROR`ログは、エラー処理をテストするための意図的な出力であり、問題ではない。

## 考えられる根本原因

1. **リソースリーク**: 
   - 非同期リソース（ファイル、ネットワーク接続）が適切にクリーンアップされていない
   - 624テスト実行後に何らかのリソース限界に到達

2. **モックオブジェクトの蓄積**:
   - グローバルモックやパッチが累積して干渉
   - `unittest.mock`のパッチがテスト間で適切にリセットされていない

3. **非同期タスクの残留**:
   - `asyncio`タスクが完了せずに残っている
   - イベントループの状態が汚染されている

4. **テスト順序依存**:
   - 特定のテストの組み合わせでのみ発生
   - 624番目のテスト後に特定の状態が作られる

## 次の調査ステップ

1. **最小再現ケースの作成**:
   - 624番目のテスト周辺のテストのみを実行
   - ハングを再現する最小のテストセットを特定

2. **リソース監視**:
   - メモリ使用量、ファイルディスクリプタ数を監視
   - `lsof`や`psutil`でリソース状態を確認

3. **非同期デバッグ**:
   - `asyncio.all_tasks()`で残留タスクを確認
   - イベントループの状態をログ出力

4. **テスト分割実行**:
   - テストを複数のジョブに分割して並列実行
   - 問題を回避しつつ原因を絞り込む

## 最終更新
2025-08-30 14:30 JST
- すべての修正試行が失敗
- 個別実行では成功するが一括実行でハング
- Geminiとの協議が必要な状態