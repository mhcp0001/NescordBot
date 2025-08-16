#!/usr/bin/env python3
"""
Railway deployment entry point for NescordBot.

This file serves as a simplified entry point specifically for Railway deployment,
avoiding complex path manipulation by using absolute imports.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional

# Ensure we can import from src directory
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.logger import get_logger
from src.config import get_config_manager
from src.bot import main as bot_main


class SimpleRunner:
    """Simplified bot runner for Railway deployment."""
    
    def __init__(self):
        self.logger = None
        self.shutdown_event = asyncio.Event()
    
    def setup_logging(self):
        """Initialize logging."""
        self.logger = get_logger("railway-runner")
        self.logger.info("Railway runner initialized")
    
    def validate_environment(self) -> bool:
        """Validate required environment variables."""
        try:
            config_manager = get_config_manager()
            config = config_manager.config
            
            self.logger.info("Environment validation successful")
            self.logger.info(f"Discord token: {'*' * 10}{config.discord_token[-4:]}")
            self.logger.info(f"OpenAI API key: {'*' * 10}{config.openai_api_key[-4:]}")
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.critical(f"Environment validation failed: {e}")
            else:
                print(f"❌ Environment validation failed: {e}")
            return False
    
    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum: int, frame):
            signal_name = signal.Signals(signum).name
            if self.logger:
                self.logger.info(f"Received {signal_name} signal, shutting down...")
            
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self._shutdown())
            else:
                self.shutdown_event.set()
        
        # Railway containers typically use SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if self.logger:
            self.logger.info("Signal handlers configured for Railway")
    
    async def _shutdown(self):
        """Set shutdown event."""
        self.shutdown_event.set()
    
    async def run(self) -> int:
        """Run the bot."""
        try:
            self.setup_logging()
            
            if not self.validate_environment():
                return 1
            
            self.setup_signal_handlers()
            
            self.logger.info("Starting NescordBot on Railway...")
            
            # Run bot with shutdown monitoring
            bot_task = asyncio.create_task(bot_main())
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            
            done, pending = await asyncio.wait(
                [bot_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Handle shutdown
            if shutdown_task in done:
                self.logger.info("Shutdown signal received, stopping bot...")
                if not bot_task.done():
                    bot_task.cancel()
                    try:
                        await asyncio.wait_for(bot_task, timeout=10.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        self.logger.warning("Bot task cancellation timed out")
                
                self.logger.info("Bot stopped successfully")
                return 0
            
            # Bot completed
            if bot_task in done:
                try:
                    await bot_task
                    self.logger.info("Bot completed normally")
                    return 0
                except Exception as e:
                    self.logger.error(f"Bot task failed: {e}")
                    return 1
            
            return 0
            
        except Exception as e:
            if self.logger:
                self.logger.critical(f"Fatal error: {e}")
            else:
                print(f"❌ Fatal error: {e}")
            return 1
        finally:
            # Cancel remaining tasks
            if 'pending' in locals():
                for task in pending:
                    if not task.done():
                        task.cancel()


def main():
    """Main entry point for Railway deployment."""
    print("🚀 Starting NescordBot on Railway...")
    
    try:
        runner = SimpleRunner()
        exit_code = asyncio.run(runner.run())
        
        if exit_code == 0:
            print("✅ Bot shutdown complete")
        else:
            print(f"❌ Bot exited with code {exit_code}")
        
        return exit_code
        
    except KeyboardInterrupt:
        print("👋 Bot stopped by signal")
        return 0
    except Exception as e:
        print(f"❌ Fatal startup error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())