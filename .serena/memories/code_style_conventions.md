# NescordBot コードスタイル・規約

## コードフォーマット設定

### Black設定（pyproject.toml）
- **行長**: 100文字
- **Pythonバージョン**: 3.11
- **除外ディレクトリ**: .eggs, .git, .mypy_cache, .tox, .venv, build, dist

### isort設定
- **プロファイル**: black（Black互換）
- **行長**: 100文字

### Ruff設定
- **行長**: 100文字
- **対象**: Python 3.11
- **有効ルール**: E（エラー）, F（flake8）, W（警告）, I（isort）
- **無視ルール**: E203（Black競合）, E501（行長）

## TypeScript/JavaScript規約（CLAUDE.md由来）
- **クラス使用禁止**: TypeScript `class` は `Error` 継承等の絶対必要時のみ
- **型注釈**: `any`, `unknown` 型の使用禁止
- **ハードコーディング回避**: 値の直接埋め込み最小化

## Python固有規約

### 型ヒント（mypy設定）
```python
# 推奨: 型ヒント使用
def process_audio(file_path: str) -> dict[str, Any]:
    pass

# 非推奨: 型ヒントなし
def process_audio(file_path):
    pass
```

### Docstring規約
```python
def transcribe_audio(file_path: str, language: str = "ja-JP") -> str:
    """音声ファイルを文字起こしする.

    Args:
        file_path: 音声ファイルのパス
        language: 認識言語（デフォルト: ja-JP）

    Returns:
        文字起こし結果テキスト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        OpenAIError: API呼び出しエラー
    """
```

### 命名規約
- **クラス**: PascalCase (`NescordBot`, `DatabaseService`)
- **関数・変数**: snake_case (`transcribe_audio`, `file_path`)
- **定数**: UPPER_SNAKE_CASE (`MAX_AUDIO_SIZE_MB`)
- **プライベート**: アンダースコア接頭辞 (`_internal_method`)

### Import順序（isort適用）
```python
# 1. 標準ライブラリ
import asyncio
import logging
from pathlib import Path

# 2. サードパーティ
import discord
from discord.ext import commands
import openai

# 3. ローカルモジュール
from nescordbot.config import Config
from nescordbot.services import DatabaseService
```

## 非同期処理規約

### async/await使用
```python
# 推奨: 適切な非同期処理
async def handle_voice_message(self, message: discord.Message) -> None:
    async with aiofiles.open(file_path, 'rb') as f:
        audio_data = await f.read()

    result = await self.transcribe_async(audio_data)
    await message.reply(result)

# 非推奨: 同期処理混在
def handle_voice_message(self, message):
    with open(file_path, 'rb') as f:  # 同期I/O
        audio_data = f.read()
```

### エラーハンドリング
```python
# 推奨: 具体的例外キャッチ
try:
    result = await openai_client.transcribe(audio)
except openai.OpenAIError as e:
    logger.error(f"OpenAI API error: {e}")
    await ctx.send("音声処理でエラーが発生しました")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    await ctx.send("予期しないエラーが発生しました")

# 非推奨: 広範囲例外キャッチ
try:
    result = await openai_client.transcribe(audio)
except Exception:  # 具体性に欠ける
    pass
```

## Discord.py規約

### Cog構造
```python
class VoiceCog(commands.Cog):
    """音声処理コマンド群."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = bot.config

    @commands.hybrid_command(name="transcribe")
    async def transcribe_command(self, ctx: commands.Context) -> None:
        """音声文字起こしコマンド."""
        pass
```

### スラッシュコマンド
```python
# 推奨: hybrid_command使用（スラッシュ・プレフィックス両対応）
@commands.hybrid_command(name="status", description="Botステータス確認")
async def status(self, ctx: commands.Context) -> None:
    pass

# 推奨: 型ヒント付きオプション
@app_commands.describe(language="認識言語（ja-JP, en-US等）")
async def transcribe(self, ctx: commands.Context, language: str = "ja-JP") -> None:
    pass
```

## テスト規約

### pytest構造
```python
# テストファイル命名: test_*.py
# tests/test_voice_cog.py

import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_transcribe_success():
    """正常な音声文字起こしテスト."""
    # Given
    mock_bot = AsyncMock()
    cog = VoiceCog(mock_bot)

    # When
    with patch('openai.Audio.transcribe') as mock_transcribe:
        mock_transcribe.return_value = {"text": "テスト結果"}
        result = await cog.process_audio("test.mp3")

    # Then
    assert result == "テスト結果"
    mock_transcribe.assert_called_once()

# スキップマーカー使用
@pytest.mark.slow
@pytest.mark.network
async def test_real_api_call():
    """実際のAPI呼び出しテスト（slow・network）."""
    pass
```

### モック使用
```python
# 推奨: 外部依存をモック
@patch('nescordbot.services.openai_client')
async def test_with_mock(mock_client):
    mock_client.transcribe.return_value = "モック結果"
    # テスト実行
```

## ファイル構成規約

### ディレクトリ構造
```
src/nescordbot/
├── __init__.py         # パッケージ初期化
├── __main__.py         # モジュール実行エントリー
├── main.py             # アプリケーション起動
├── bot.py              # Bot本体
├── config.py           # 設定管理
├── logger.py           # ログ設定
├── cogs/               # コマンド機能群
│   ├── __init__.py
│   ├── general.py      # 汎用コマンド
│   ├── voice.py        # 音声処理
│   └── admin.py        # 管理機能
└── services/           # 外部サービス統合
    ├── __init__.py     # サービスコンテナ
    ├── database.py     # DB操作
    └── github.py       # GitHub API
```

### ファイル命名
- **モジュール**: snake_case (`voice_processor.py`)
- **設定ファイル**: 機能明示 (`config.py`, `logger.py`)
- **テスト**: `test_` 接頭辞 (`test_voice_cog.py`)

## 設定・環境管理

### Pydantic設定クラス
```python
from pydantic import BaseSettings

class Config(BaseSettings):
    """アプリケーション設定."""

    discord_token: str
    openai_api_key: str
    log_level: str = "INFO"
    max_audio_size_mb: int = 25

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```
