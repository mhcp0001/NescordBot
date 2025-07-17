import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import logging
from datetime import datetime
import aiohttp

# 環境変数の読み込み
load_dotenv()

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Botの設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

class NescordBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None  # カスタムヘルプコマンドを使用
        )
        
    async def setup_hook(self):
        """Bot起動時の初期設定"""
        # Cogsの読み込み
        await self.load_extension('cogs.general')
        await self.load_extension('cogs.voice')
        
        # スラッシュコマンドの同期
        await self.tree.sync()
        logger.info(f"Synced {len(self.tree.get_commands())} slash commands")
        
    async def on_ready(self):
        """Bot起動完了時の処理"""
        logger.info(f'{self.user} (ID: {self.user.id}) が起動しました！')
        
        # ステータスの設定
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="音声メッセージ"
            )
        )
        
    async def on_message(self, message):
        """メッセージ受信時の処理"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return
            
        # 音声メッセージの処理
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and 'audio' in attachment.content_type:
                    await self.process_voice_message(message, attachment)
                    
        # コマンド処理
        await self.process_commands(message)
        
    async def process_voice_message(self, message, attachment):
        """音声メッセージの処理"""
        try:
            # 処理中のリアクションを追加
            await message.add_reaction('⏳')
            
            logger.info(f'音声メッセージを検出: {attachment.filename}')
            
            # 音声ファイルをダウンロード
            audio_data = await attachment.read()
            
            # 一時ファイルとして保存
            temp_path = os.path.join('data', f'temp_{message.id}.ogg')
            os.makedirs('data', exist_ok=True)
            
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
                
            # ここに音声認識処理を追加
            # transcription = await transcribe_audio(temp_path)
            
            # 仮の応答（実際は音声認識結果を使用）
            embed = discord.Embed(
                title="🎤 音声メッセージを受信しました",
                description="音声認識機能は現在実装中です。",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="ファイル名",
                value=attachment.filename,
                inline=True
            )
            embed.add_field(
                name="サイズ",
                value=f"{attachment.size / 1024:.1f} KB",
                inline=True
            )
            embed.set_footer(text=f"送信者: {message.author.name}")
            
            await message.reply(embed=embed)
            
            # 処理完了のリアクション
            await message.remove_reaction('⏳', self.user)
            await message.add_reaction('✅')
            
            # 一時ファイルを削除
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        except Exception as e:
            logger.error(f'音声メッセージ処理エラー: {e}')
            await message.remove_reaction('⏳', self.user)
            await message.add_reaction('❌')
            await message.reply(f'エラーが発生しました: {str(e)}')

def main():
    """メイン関数"""
    # Botトークンの確認
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('DISCORD_TOKENが設定されていません。')
        return
        
    # Bot インスタンスの作成と起動
    bot = NescordBot()
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        logger.error('無効なトークンです。')
    except Exception as e:
        logger.error(f'予期しないエラー: {e}')

if __name__ == '__main__':
    main()
