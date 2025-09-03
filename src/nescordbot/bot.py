"""
NescordBot - Discord bot with voice transcription and AI-powered features.

This module contains the main bot implementation using discord.py with
integrated configuration management and logging services.
"""

import asyncio
import traceback
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from .config import get_config_manager
from .logger import get_logger
from .security import SecurityValidator
from .services import (
    AlertManager,
    APIMonitor,
    BatchProcessor,
    DatabaseService,
    EmbeddingService,
    FallbackManager,
    GitHubAuthManager,
    GitHubService,
    GitOperationService,
    KnowledgeManager,
    NoteProcessingService,
    ObsidianGitHubService,
    Phase4Monitor,
    SearchEngine,
    SyncManager,
    TokenManager,
    create_service_container,
)


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

        # Initialize GitHub service if configured
        self.github_service: Optional[GitHubService] = None
        if (
            self.config.github_token
            and self.config.github_repo_owner
            and self.config.github_repo_name
        ):
            self.github_service = GitHubService(self.config)
            self.logger.info("GitHub service initialized")
        else:
            self.logger.info("GitHub integration disabled (missing configuration)")

        # Initialize NoteProcessingService
        self.note_processing_service = NoteProcessingService()
        self.logger.info("NoteProcessingService initialized")

        # Initialize ObsidianGitHub integration services
        self._init_obsidian_services()

        # Initialize ServiceContainer with Phase 4 services
        self._init_service_container()

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

            # Start GitHub service if available
            if self.github_service:
                await self.github_service.start()
                self.logger.info("GitHub service started")

            # Initialize ObsidianGitHub services if available
            await self._init_obsidian_services_async()

            # Initialize and start Phase 4 monitoring services
            if self.service_container:
                try:
                    # Initialize services
                    await self.service_container.initialize_services()
                    self.logger.info("ServiceContainer services initialized")

                    # Start Phase4Monitor if available
                    if self.service_container.has_service(Phase4Monitor):
                        phase4_monitor = self.service_container.get_service(Phase4Monitor)
                        await phase4_monitor.start_monitoring()
                        self.logger.info("Phase4Monitor started")

                    # Start AlertManager if available and enabled
                    if self.service_container.has_service(AlertManager) and getattr(
                        self.config, "alert_enabled", True
                    ):
                        alert_manager = self.service_container.get_service(AlertManager)
                        await alert_manager.start_monitoring()
                        self.logger.info("AlertManager started")

                except Exception as e:
                    self.logger.error(f"Failed to initialize Phase 4 services: {e}")

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

        # Stop GitHub service
        if hasattr(self, "github_service") and self.github_service:
            await self.github_service.stop()
            self.logger.info("GitHub service stopped")

        # Stop ObsidianGitHub services
        if hasattr(self, "obsidian_service") and self.obsidian_service:
            await self.obsidian_service.shutdown()
            self.logger.info("ObsidianGitHub service stopped")

        # Shutdown ServiceContainer services
        if hasattr(self, "service_container") and self.service_container:
            try:
                # Stop AlertManager if running
                if self.service_container.has_service(AlertManager):
                    alert_manager = self.service_container.get_service(AlertManager)
                    await alert_manager.close()
                    self.logger.info("AlertManager stopped")

                # Stop Phase4Monitor if running
                if self.service_container.has_service(Phase4Monitor):
                    phase4_monitor = self.service_container.get_service(Phase4Monitor)
                    await phase4_monitor.close()
                    self.logger.info("Phase4Monitor stopped")

                # Shutdown all services
                await self.service_container.shutdown_services()
                self.logger.info("ServiceContainer services stopped")

            except Exception as e:
                self.logger.error(f"Error shutting down ServiceContainer: {e}")

        await super().close()
        self.logger.info("Bot shutdown complete")

    def _init_obsidian_services(self) -> None:
        """Initialize ObsidianGitHub integration services (synchronous part)."""
        self.obsidian_service: Optional[ObsidianGitHubService] = None

        # Check if ObsidianGitHub integration should be enabled
        obsidian_enabled = getattr(self.config, "github_obsidian_enabled", False)
        if not obsidian_enabled:
            self.logger.info("ObsidianGitHub integration disabled (github_obsidian_enabled=False)")
            self.logger.info("To enable: Set GITHUB_OBSIDIAN_ENABLED=true in environment variables")
            return

        # Check required configuration
        required_config = ["github_token", "github_repo_owner", "github_repo_name"]

        missing_config = [key for key in required_config if not getattr(self.config, key, None)]
        if missing_config:
            self.logger.warning(
                f"ObsidianGitHub integration disabled (missing config: {missing_config})"
            )
            self.logger.warning("Required environment variables:")
            for key in missing_config:
                env_key = key.upper()
                self.logger.warning(f"  - {env_key}")
            return

        try:
            # Initialize SecurityValidator
            self.security_validator = SecurityValidator()

            # Initialize GitHub Auth Manager
            self.github_auth_manager = GitHubAuthManager(self.config)

            # Initialize Git Operations Service
            self.git_operations = GitOperationService(self.config, self.github_auth_manager)

            # Initialize Batch Processor
            self.batch_processor = BatchProcessor(
                self.config, self.database_service, self.github_auth_manager, self.git_operations
            )

            # Initialize ObsidianGitHub Service
            self.obsidian_service = ObsidianGitHubService(
                self.config, self.batch_processor, self.security_validator
            )

            self.logger.info("ObsidianGitHub services initialized (async initialization pending)")

        except Exception as e:
            self.logger.error(f"Failed to initialize ObsidianGitHub services: {e}")
            self.obsidian_service = None

    async def _init_obsidian_services_async(self) -> None:
        """Initialize ObsidianGitHub integration services (asynchronous part)."""
        if not self.obsidian_service:
            return

        try:
            # Initialize services in order
            await self.github_auth_manager.initialize()
            await self.git_operations.initialize()
            await self.batch_processor.initialize()
            await self.obsidian_service.initialize()

            self.logger.info("ObsidianGitHub services fully initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize ObsidianGitHub services async: {e}")
            # Clean up partially initialized services
            self.obsidian_service = None

    def _init_service_container(self) -> None:
        """Initialize ServiceContainer with Phase 4 services."""
        try:
            # Create service container
            self.service_container = create_service_container(self.config)

            # Register EmbeddingService factory
            def create_embedding_service() -> EmbeddingService:
                return EmbeddingService(self.config)

            self.service_container.register_factory(EmbeddingService, create_embedding_service)

            # Register ChromaDBService factory
            from .services.chromadb_service import ChromaDBService

            def create_chromadb_service() -> ChromaDBService:
                return ChromaDBService(self.config)

            self.service_container.register_factory(ChromaDBService, create_chromadb_service)

            # Register TokenManager factory
            def create_token_manager() -> TokenManager:
                return TokenManager(self.config, self.database_service)

            self.service_container.register_factory(TokenManager, create_token_manager)

            # Register SyncManager factory
            def create_sync_manager() -> SyncManager:
                # Get dependencies from service container
                embedding_service = self.service_container.get_service(EmbeddingService)
                chromadb_service = self.service_container.get_service(ChromaDBService)
                return SyncManager(
                    self.config, self.database_service, chromadb_service, embedding_service
                )

            self.service_container.register_factory(SyncManager, create_sync_manager)

            # KnowledgeManager factory
            def create_knowledge_manager() -> KnowledgeManager:
                database_service = self.database_service
                chromadb_service = self.service_container.get_service(ChromaDBService)
                embedding_service = self.service_container.get_service(EmbeddingService)
                sync_manager = self.service_container.get_service(SyncManager)
                obsidian_github_service = self.service_container.get_service(ObsidianGitHubService)
                return KnowledgeManager(
                    self.config,
                    database_service,
                    chromadb_service,
                    embedding_service,
                    sync_manager,
                    obsidian_github_service,
                )

            def create_search_engine() -> SearchEngine:
                database_service = self.database_service
                chromadb_service = self.service_container.get_service(ChromaDBService)
                embedding_service = self.service_container.get_service(EmbeddingService)
                return SearchEngine(
                    chroma_service=chromadb_service,
                    db_service=database_service,
                    embedding_service=embedding_service,
                    config=self.config,
                )

            self.service_container.register_factory(KnowledgeManager, create_knowledge_manager)
            self.service_container.register_factory(SearchEngine, create_search_engine)

            # FallbackManager factory
            def create_fallback_manager() -> FallbackManager:
                from .services.fallback_manager import FallbackManager

                return FallbackManager(self.config)

            self.service_container.register_factory(FallbackManager, create_fallback_manager)

            # APIMonitor factory (depends on TokenManager and FallbackManager)
            def create_api_monitor() -> APIMonitor:
                from .services.api_monitor import APIMonitor

                token_manager = self.service_container.get_service(TokenManager)
                fallback_manager = self.service_container.get_service(FallbackManager)
                return APIMonitor(self.config, token_manager, fallback_manager)

            self.service_container.register_factory(APIMonitor, create_api_monitor)

            # Phase4Monitor factory (depends on multiple services)
            def create_phase4_monitor() -> Phase4Monitor:
                from .services.phase4_monitor import Phase4Monitor

                token_manager = self.service_container.get_service(TokenManager)
                api_monitor = self.service_container.get_service(APIMonitor)
                search_engine = self.service_container.get_service(SearchEngine)
                knowledge_manager = self.service_container.get_service(KnowledgeManager)
                chromadb_service = self.service_container.get_service(ChromaDBService)
                return Phase4Monitor(
                    config=self.config,
                    token_manager=token_manager,
                    api_monitor=api_monitor,
                    search_engine=search_engine,
                    knowledge_manager=knowledge_manager,
                    chromadb_service=chromadb_service,
                    database_service=self.database_service,
                )

            self.service_container.register_factory(Phase4Monitor, create_phase4_monitor)

            # AlertManager factory (depends on Phase4Monitor and TokenManager)
            def create_alert_manager() -> AlertManager:
                from .services.alert_manager import AlertManager

                phase4_monitor = self.service_container.get_service(Phase4Monitor)
                token_manager = self.service_container.get_service(TokenManager)
                return AlertManager(
                    config=self.config,
                    bot=self,  # Pass the bot instance for Discord notifications
                    database_service=self.database_service,
                    phase4_monitor=phase4_monitor,
                    token_manager=token_manager,
                )

            self.service_container.register_factory(AlertManager, create_alert_manager)

            self.logger.info(
                "ServiceContainer initialized with EmbeddingService, ChromaDBService, "
                "TokenManager, SyncManager, KnowledgeManager, SearchEngine, FallbackManager, "
                "APIMonitor, Phase4Monitor, and AlertManager"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize ServiceContainer: {e}")
            self.service_container = None  # type: ignore[assignment]  # type: ignore[assignment]


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
