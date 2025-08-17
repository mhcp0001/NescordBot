"""
NescordBot - Discord bot with voice transcription and AI-powered features.

This module contains the main bot implementation using discord.py with
integrated configuration management and logging services.
"""

import asyncio
import traceback
from pathlib import Path

import discord
from discord.ext import commands

from .config import get_config_manager
from .logger import get_logger
from .services import DatabaseService


class NescordBot(commands.Bot):
    """
    Main Discord bot class with voice transcription and AI features.

    Inherits from discord.py commands.Bot and integrates with ConfigManager
    and LoggerService for centralized configuration and logging.
    """

    def __init__(self):
        """Initialize the NescordBot with proper configuration."""
        # Get configuration
        self.config_manager = get_config_manager()
        self.config = self.config_manager.config

        # Get logger
        self.logger = get_logger("bot")

        # Set up Discord intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True

        super().__init__(
            command_prefix="!",  # Prefix for text commands (mostly for debugging)
            intents=intents,
            help_command=None,  # We'll implement custom help
            case_insensitive=True,
        )

        # Create data directory for temporary files
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

        # Initialize database service
        db_path = self.config.database_url if hasattr(self.config, "database_url") else "nescord.db"
        self.database_service = DatabaseService(db_path)

        self.logger.info("NescordBot instance created")

    async def setup_hook(self) -> None:
        """
        Set up the bot after login but before connecting to Discord.

        This method is called automatically by discord.py and is used to
        load cogs and sync application commands.
        """
        self.logger.info("Starting bot setup...")

        try:
            # Initialize database service
            await self.database_service.initialize()
            self.logger.info("Database service initialized")

            # Load cogs
            await self._load_cogs()

            # Sync application commands
            await self._sync_commands()

            self.logger.info("Bot setup completed successfully")

        except Exception as e:
            self.logger.error(f"Error during bot setup: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def _load_cogs(self) -> None:
        """Load all cogs from the cogs directory."""
        cogs_dir = Path(__file__).parent / "cogs"
        cogs_loaded = 0

        if not cogs_dir.exists():
            self.logger.warning("Cogs directory not found")
            return

        # Load cogs from files
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.name.startswith("__"):
                continue

            cog_name = f"nescordbot.cogs.{cog_file.stem}"

            try:
                await self.load_extension(cog_name)
                cogs_loaded += 1
                self.logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                self.logger.error(f"Failed to load cog {cog_name}: {e}")

        self.logger.info(f"Loaded {cogs_loaded} cogs")

    async def _sync_commands(self) -> None:
        """Sync application commands with Discord."""
        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synced {len(synced)} application commands")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self) -> None:
        """Handle bot ready event."""
        if self.user:
            self.logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Connected to {len(self.guilds)} guilds")

        # Set bot presence
        activity = discord.Activity(type=discord.ActivityType.listening, name="音声メッセージ | /help")
        await self.change_presence(activity=activity, status=discord.Status.online)

        self.logger.info("Bot is ready and online!")

    async def on_message(self, message: discord.Message) -> None:
        """
        Handle incoming messages.

        This method processes voice message attachments and regular commands.
        """
        # Ignore messages from bots
        if message.author.bot:
            return

        # Log message for debugging (without content for privacy)
        self.logger.debug(
            f"Message from {message.author} in {message.guild}/{message.channel} "
            f"with {len(message.attachments)} attachments"
        )

        # Process voice attachments
        await self._process_voice_attachments(message)

        # Process regular commands
        await self.process_commands(message)

    async def _process_voice_attachments(self, message: discord.Message) -> None:
        """Process voice message attachments."""
        if not message.attachments:
            return

        for attachment in message.attachments:
            # Check if it's an audio file
            if self._is_audio_file(attachment):
                await self._handle_voice_message(message, attachment)

    def _is_audio_file(self, attachment: discord.Attachment) -> bool:
        """Check if an attachment is an audio file."""
        # Check content type
        if attachment.content_type and "audio" in attachment.content_type:
            return True

        # Check file extension
        audio_extensions = {".ogg", ".mp3", ".wav", ".m4a", ".webm", ".mp4"}
        file_ext = Path(attachment.filename).suffix.lower()

        return file_ext in audio_extensions

    async def _handle_voice_message(
        self, message: discord.Message, attachment: discord.Attachment
    ) -> None:
        """Handle a voice message attachment."""
        try:
            # Check file size limit
            max_size_mb = self.config.max_audio_size_mb
            max_size_bytes = max_size_mb * 1024 * 1024

            if attachment.size > max_size_bytes:
                await message.reply(f"⚠️ 音声ファイルが大きすぎます。" f"最大サイズ: {max_size_mb}MB")
                return

            # Add processing reaction
            await message.add_reaction("⏳")

            self.logger.info(
                f"Processing voice message: {attachment.filename} "
                f"({attachment.size} bytes) from {message.author}"
            )

            # For now, just acknowledge the voice message
            # Voice processing will be implemented in later tasks
            await self._send_voice_acknowledgment(message, attachment)

            # Remove processing reaction and add success reaction
            if self.user:
                await message.remove_reaction("⏳", self.user)
            await message.add_reaction("✅")

        except Exception as e:
            self.logger.error(f"Error processing voice message: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")

            # Remove processing reaction and add error reaction
            try:
                if self.user:
                    await message.remove_reaction("⏳", self.user)
                await message.add_reaction("❌")
                await message.reply("❌ 音声メッセージの処理中にエラーが発生しました。")
            except Exception as reaction_error:
                self.logger.error(f"Error updating reactions: {reaction_error}")

    async def _send_voice_acknowledgment(
        self, message: discord.Message, attachment: discord.Attachment
    ) -> None:
        """Send acknowledgment for voice message."""
        embed = discord.Embed(
            title="🎤 音声メッセージを受信しました",
            description="音声認識機能は開発中です。今後のアップデートをお待ちください。",
            color=discord.Color.blue(),
        )
        embed.add_field(name="ファイル名", value=attachment.filename, inline=True)
        embed.add_field(name="サイズ", value=f"{attachment.size / 1024:.1f} KB", inline=True)
        embed.add_field(name="形式", value=attachment.content_type or "不明", inline=True)
        embed.set_footer(text=f"送信者: {message.author.display_name}")
        embed.timestamp = message.created_at

        await message.reply(embed=embed)

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Handle global bot errors."""
        self.logger.error(f"Unhandled error in event {event}")
        self.logger.error(f"Args: {args}")
        self.logger.error(f"Kwargs: {kwargs}")
        self.logger.error(f"Traceback: {traceback.format_exc()}")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            # Ignore command not found errors
            return

        self.logger.error(
            f"Command error in {ctx.command}: {error} " f"(User: {ctx.author}, Guild: {ctx.guild})"
        )

        # Send user-friendly error message
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("❌ 必要な引数が不足しています。")
        elif isinstance(error, commands.BadArgument):
            await ctx.reply("❌ 引数の形式が正しくありません。")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ この操作を実行する権限がありません。")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.reply("❌ Botにこの操作を実行する権限がありません。")
        else:
            await ctx.reply("❌ コマンドの実行中にエラーが発生しました。")

    async def close(self) -> None:
        """Clean up resources when bot is shutting down."""
        self.logger.info("Bot is shutting down...")

        # Close database service
        if hasattr(self, "database_service") and self.database_service.is_initialized:
            await self.database_service.close()
            self.logger.info("Database service closed")

        await super().close()
        self.logger.info("Bot shutdown complete")


async def main() -> None:
    """
    Main function to run the bot.

    This function handles bot initialization, configuration validation,
    and graceful shutdown.
    """
    # Get logger for main function
    logger = get_logger("main")

    try:
        # Validate configuration
        config_manager = get_config_manager()
        config = config_manager.config  # This will raise ValidationError if invalid

        logger.info("Configuration validated successfully")
        logger.info(f"Log level: {config.log_level}")
        logger.info(f"Max audio size: {config.max_audio_size_mb}MB")
        logger.info(f"Speech language: {config.speech_language}")

        # Create and run bot
        bot = NescordBot()

        async with bot:
            await bot.start(config.discord_token)

    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        logger.critical(f"Traceback: {traceback.format_exc()}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        exit(1)
