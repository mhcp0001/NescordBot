"""
NescordBot - Discord Bot with voice transcription and AI-powered features.

This package provides a Discord bot that can transcribe voice messages
using OpenAI's Whisper API and process text with GPT models.
"""

__version__ = "1.0.0"
__author__ = "NescordBot Team"

# Package-level imports for convenience
from .bot import NescordBot
from .config import BotConfig, get_config_manager
from .logger import get_logger

__all__ = ["NescordBot", "BotConfig", "get_config_manager", "get_logger"]
