import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import platform
import psutil
import os

class General(commands.Cog):
    """一般的なコマンドを管理するCog"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="help", description="Botの使い方を表示します")
    async def help_command(self, interaction: discord.Interaction):
        """ヘルプコマンド"""
        embed = discord.Embed(
            title="📖 Nescordbot ヘルプ",
            description="Discord Bot with voice transcription and AI features",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🎤 音声メッセージ機能",
            value="音声メッセージを送信すると、自動的に文字起こしされます。",
            inline=False
        )
        
        embed.add_field(
            name="📝 スラッシュコマンド",
            value=(
                "`/help` - このヘルプを表示\n"
                "`/status` - Botのステータスを確認\n"
                "`/ping` - Botの応答速度を確認\n"
                "`/search [keyword]` - メモを検索（実装予定）"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value=(
                "• 音声は日本語で話してください\n"
                "• 最大25MBまでの音声ファイルに対応\n"
                "• 文字起こし後、AIが内容を整形します"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made with ❤️ using discord.py")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="status", description="Botのステータスを表示します")
    async def status_command(self, interaction: discord.Interaction):
        """ステータスコマンド"""
        # システム情報の取得
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Bot情報
        latency = round(self.bot.latency * 1000)
        guild_count = len(self.bot.guilds)
        user_count = sum(guild.member_count for guild in self.bot.guilds)
        
        embed = discord.Embed(
            title="📊 Bot Status",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🤖 Bot情報",
            value=(
                f"**レイテンシ:** {latency}ms\n"
                f"**サーバー数:** {guild_count}\n"
                f"**ユーザー数:** {user_count:,}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="💻 システム情報",
            value=(
                f"**CPU使用率:** {cpu_percent}%\n"
                f"**メモリ使用率:** {memory.percent}%\n"
                f"**ディスク使用率:** {disk.percent}%"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🐍 環境情報",
            value=(
                f"**Python:** {platform.python_version()}\n"
                f"**discord.py:** {discord.__version__}\n"
                f"**OS:** {platform.system()}"
            ),
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="ping", description="Botの応答速度を確認します")
    async def ping_command(self, interaction: discord.Interaction):
        """Pingコマンド"""
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"レイテンシ: **{latency}ms**",
            color=discord.Color.green() if latency < 100 else discord.Color.yellow()
        )
        
        await interaction.response.send_message(embed=embed)
        
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """コマンドエラーハンドリング"""
        if isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ このコマンドを実行する権限がありません。")
            return
            
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ 必要な引数が不足しています: `{error.param.name}`")
            return
            
        # その他のエラー
        await ctx.send(f"❌ エラーが発生しました: {str(error)}")
        
        # ログに記録
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Command error: {error}", exc_info=True)

async def setup(bot):
    """Cogをセットアップ"""
    await bot.add_cog(General(bot))
