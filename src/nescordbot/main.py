#!/usr/bin/env python3
"""
NescordBot main entry point.

This module serves as the main entry point for the NescordBot application.
It handles initialization, configuration validation, signal handling,
and graceful shutdown.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from .bot import main as bot_main
from .config import get_config_manager
from .logger import get_logger


class BotRunner:
    """
    Bot runner that handles the application lifecycle.

    Manages initialization, startup, signal handling, and graceful shutdown.
    """

    def __init__(self):
        """Initialize the bot runner."""
        self.bot = None
        self.logger: Optional[logging.Logger] = None  # Will be initialized in setup_logging
        self.shutdown_event = asyncio.Event()

    def setup_logging(self) -> None:
        """Set up logging for the runner."""
        try:
            self.logger = get_logger("runner")
            self.logger.info("Bot runner initialized")
        except Exception as e:
            print(f"❌ Failed to initialize logging: {e}")
            sys.exit(1)

    def validate_environment(self) -> bool:
        """
        Validate required environment variables and configuration.

        Returns:
            bool: True if environment is valid, False otherwise
        """
        try:
            if self.logger:
                self.logger.info("Validating environment configuration...")

            # Check if .env file exists (optional but recommended)
            env_file = Path(".env")
            if env_file.exists():
                if self.logger:
                    self.logger.info("Found .env file")
            else:
                if self.logger:
                    self.logger.warning("No .env file found - using system environment variables")

            # Validate configuration
            config_manager = get_config_manager()
            config = config_manager.config  # This will raise ValidationError if invalid

            if self.logger:
                self.logger.info("Environment validation successful")
                self.logger.info(f"Discord token: {'*' * 10}{config.discord_token[-4:]}")
                self.logger.info(f"OpenAI API key: {'*' * 10}{config.openai_api_key[-4:]}")
                self.logger.info(f"Log level: {config.log_level}")
                self.logger.info(f"Max audio size: {config.max_audio_size_mb}MB")
                self.logger.info(f"Speech language: {config.speech_language}")

            return True

        except Exception as e:
            if self.logger:
                self.logger.critical(f"Environment validation failed: {e}")
            else:
                print(f"❌ Environment validation failed: {e}")

            self._print_setup_help()
            return False

    def _print_setup_help(self) -> None:
        """Print helpful setup information when validation fails."""
        print("\n" + "=" * 60)
        print("🔧 SETUP HELP")
        print("=" * 60)
        print("\n1. Create a .env file based on .env.example:")
        print("   cp .env.example .env")
        print("\n2. Edit .env and set your tokens:")
        print("   DISCORD_TOKEN=your_discord_bot_token")
        print("   OPENAI_API_KEY=your_openai_api_key")
        print("\n3. Discord Bot Setup:")
        print("   - Go to https://discord.com/developers/applications")
        print("   - Create a new application")
        print("   - Go to Bot section and copy the token")
        print("\n4. OpenAI API Setup:")
        print("   - Go to https://platform.openai.com/api-keys")
        print("   - Create a new API key")
        print("\n5. Run the bot:")
        print("   poetry run nescordbot")
        print("\n" + "=" * 60)

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame) -> None:
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            if self.logger:
                self.logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
            else:
                print(f"Received {signal_name} signal, initiating graceful shutdown...")

            # Set the shutdown event
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self._shutdown())
            else:
                self.shutdown_event.set()

        # Set up signal handlers for graceful shutdown
        if sys.platform != "win32":
            # Unix-like systems
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            # Windows
            signal.signal(signal.SIGINT, signal_handler)
            # SIGBREAK is Windows-specific, check if available
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, signal_handler)

        if self.logger:
            self.logger.info("Signal handlers configured")

    async def _shutdown(self) -> None:
        """Initiate shutdown sequence."""
        self.shutdown_event.set()

    async def run_bot(self) -> int:
        """
        Run the bot with proper error handling.

        Returns:
            int: Exit code (0 for success, non-zero for error)
        """
        try:
            if self.logger:
                self.logger.info("Starting NescordBot...")

            # Create task for bot and shutdown monitoring
            bot_task = asyncio.create_task(bot_main())
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())

            # Wait for either bot completion or shutdown signal
            done, pending = await asyncio.wait(
                [bot_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Handle shutdown
            if shutdown_task in done:
                if self.logger:
                    self.logger.info("Shutdown signal received, stopping bot...")

                # Cancel the bot task
                if not bot_task.done():
                    bot_task.cancel()
                    try:
                        await asyncio.wait_for(bot_task, timeout=10.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        if self.logger:
                            self.logger.warning("Bot task cancellation timed out")

                if self.logger:
                    self.logger.info("Bot stopped successfully")
                return 0

            # Bot completed normally (shouldn't happen usually)
            if bot_task in done:
                try:
                    await bot_task
                    if self.logger:
                        self.logger.info("Bot completed normally")
                    return 0
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Bot task failed: {e}")
                    return 1

            return 0

        except KeyboardInterrupt:
            if self.logger:
                self.logger.info("Keyboard interrupt received")
            return 0
        except Exception as e:
            if self.logger:
                self.logger.critical(f"Unexpected error during bot execution: {e}")
            else:
                print(f"❌ Unexpected error during bot execution: {e}")
            return 1
        finally:
            # Cancel any remaining tasks
            if "pending" in locals():
                for task in pending:
                    if not task.done():
                        task.cancel()

    async def start(self) -> int:
        """
        Start the bot runner.

        Returns:
            int: Exit code
        """
        try:
            # Setup logging
            self.setup_logging()

            # Validate environment
            if not self.validate_environment():
                return 1

            # Setup signal handlers
            self.setup_signal_handlers()

            # Run the bot
            return await self.run_bot()

        except Exception as e:
            if self.logger:
                self.logger.critical(f"Fatal error in bot runner: {e}")
            else:
                print(f"❌ Fatal error in bot runner: {e}")
            return 1


def main() -> int:
    """
    Main entry point for the application.

    Returns:
        int: Exit code
    """
    print("🚀 Starting NescordBot...")
    print("=" * 50)

    try:
        runner = BotRunner()
        return asyncio.run(runner.start())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Fatal startup error: {e}")
        return 1
