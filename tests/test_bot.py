import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# テスト用にsrcディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bot import NescordBot


@pytest.fixture
async def bot():
    """Botインスタンスのフィクスチャ"""
    with patch.dict(os.environ, {'DISCORD_TOKEN': 'test_token'}):
        bot = NescordBot()
        yield bot
        await bot.close()


@pytest.mark.asyncio
async def test_bot_initialization(bot):
    """Botの初期化テスト"""
    assert bot.command_prefix == '!'
    assert isinstance(bot.intents, discord.Intents)


@pytest.mark.asyncio
async def test_on_ready():
    """on_readyイベントのテスト"""
    bot = NescordBot()
    bot.user = MagicMock()
    bot.user.name = 'TestBot'
    bot.user.id = 123456789
    bot.change_presence = AsyncMock()
    
    await bot.on_ready()
    
    bot.change_presence.assert_called_once()


@pytest.mark.asyncio
async def test_process_voice_message():
    """音声メッセージ処理のテスト"""
    bot = NescordBot()
    
    # モックメッセージとアタッチメントを作成
    message = MagicMock()
    message.id = 123
    message.author.name = 'TestUser'
    message.add_reaction = AsyncMock()
    message.remove_reaction = AsyncMock()
    message.reply = AsyncMock()
    
    attachment = MagicMock()
    attachment.filename = 'test_audio.ogg'
    attachment.size = 1024
    attachment.read = AsyncMock(return_value=b'fake audio data')
    
    # 一時ファイルのモック
    with patch('os.makedirs'), \
         patch('builtins.open', create=True), \
         patch('os.path.exists', return_value=True), \
         patch('os.remove'):
        
        await bot.process_voice_message(message, attachment)
        
        # リアクションが追加されたか確認
        message.add_reaction.assert_called()
        message.reply.assert_called()
