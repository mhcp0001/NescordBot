"""
Configuration management for NescordBot.

This module provides centralized configuration management using Pydantic
for type validation and python-dotenv for environment variable loading.
"""

import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator


class BotConfig(BaseModel):
    """
    Bot configuration model with validation.

    All configuration values are loaded from environment variables.
    Required values will raise ValidationError if not provided.
    """

    # Required settings
    discord_token: str = Field(..., description="Discord bot token")
    openai_api_key: str = Field(..., description="OpenAI API key for Whisper and GPT")

    # Phase 4: Gemini API settings
    gemini_api_key: Optional[str] = Field(
        default=None, description="Gemini API key for Phase 4 PKM features"
    )
    gemini_monthly_limit: int = Field(
        default=50000, description="Monthly token limit for Gemini API"
    )
    gemini_requests_per_minute: int = Field(
        default=15, description="Request rate limit per minute for Gemini API"
    )

    # Optional settings with defaults
    log_level: str = Field(default="INFO", description="Logging level")
    max_audio_size_mb: int = Field(default=25, description="Maximum audio file size in MB")
    speech_language: str = Field(default="ja", description="Speech recognition language")

    # Database settings (for future use)
    database_url: str = Field(default="sqlite:///data/nescordbot.db", description="Database URL")

    # Phase 4: ChromaDB settings
    chromadb_persist_directory: str = Field(
        default="data/chromadb", description="ChromaDB persistent storage directory"
    )
    chromadb_collection_name: str = Field(
        default="nescord_knowledge", description="ChromaDB collection name for knowledge storage"
    )
    chromadb_distance_metric: str = Field(
        default="cosine", description="ChromaDB distance metric (cosine, l2, ip)"
    )
    chromadb_max_batch_size: int = Field(
        default=100, description="Maximum batch size for ChromaDB operations"
    )

    # GitHub integration settings
    github_token: Optional[str] = Field(default=None, description="GitHub API token")
    github_repo_owner: Optional[str] = Field(default=None, description="GitHub repository owner")
    github_repo_name: Optional[str] = Field(default=None, description="GitHub repository name")

    # Obsidian integration settings
    obsidian_vault_path: Optional[str] = Field(default=None, description="Obsidian vault path")

    # GitHub Obsidian integration settings
    github_obsidian_enabled: bool = Field(
        default=False, description="Enable GitHub-Obsidian integration"
    )
    github_obsidian_base_path: str = Field(
        default="obsidian_sync", description="Base path for GitHub-Obsidian sync"
    )
    github_obsidian_branch: str = Field(
        default="main", description="GitHub branch for Obsidian sync"
    )
    github_obsidian_batch_size: int = Field(
        default=10, description="Batch size for GitHub operations"
    )
    github_obsidian_batch_interval: int = Field(
        default=300, description="Batch processing interval in seconds"
    )

    # Instance management settings
    instance_id: Optional[str] = Field(
        default=None, description="Unique instance identifier for multi-instance setups"
    )

    # Security settings
    max_file_size_kb: int = Field(
        default=1024, description="Maximum file size in KB for security validation"
    )
    enable_content_validation: bool = Field(
        default=True, description="Enable content security validation"
    )

    # Phase 4: PKM feature settings
    pkm_enabled: bool = Field(
        default=False, description="Enable Personal Knowledge Management features"
    )
    hybrid_search_enabled: bool = Field(
        default=True, description="Enable hybrid search (vector + keyword)"
    )
    hybrid_search_alpha: float = Field(
        default=0.7, description="Vector search weight in hybrid search (0.0-1.0)"
    )
    max_search_results: int = Field(
        default=10, description="Maximum number of search results to return"
    )
    embedding_dimension: int = Field(default=768, description="Embedding vector dimension")

    # Phase 4: Advanced RRF settings
    rrf_k_value: int = Field(
        default=60, description="RRF constant value for rank fusion (typically 20-100)"
    )
    enable_dynamic_rrf_k: bool = Field(
        default=True, description="Enable dynamic RRF k value adjustment"
    )
    search_cache_enabled: bool = Field(default=True, description="Enable search result caching")
    search_cache_ttl_seconds: int = Field(default=300, description="Search cache TTL in seconds")

    # Phase 4: API migration mode settings
    ai_api_mode: str = Field(default="openai", description="AI API mode: openai, gemini, or hybrid")
    enable_api_fallback: bool = Field(
        default=True, description="Enable fallback between OpenAI and Gemini APIs"
    )
    api_timeout_seconds: int = Field(default=30, description="API request timeout in seconds")
    max_retry_attempts: int = Field(default=3, description="Maximum retry attempts for API calls")

    # Phase 4: AlertManager settings
    alert_enabled: bool = Field(default=True, description="Enable alert monitoring system")
    alert_channel_id: Optional[int] = Field(
        default=None, description="Discord channel ID for alert notifications"
    )
    alert_monitoring_interval: int = Field(
        default=300, description="Alert monitoring interval in seconds"
    )
    alert_default_cooldown: int = Field(default=30, description="Default alert cooldown in minutes")
    alert_max_history_size: int = Field(
        default=100, description="Maximum number of alerts to keep in history"
    )
    alert_memory_threshold_mb: int = Field(
        default=500, description="Memory usage threshold for alerts in MB"
    )
    alert_token_threshold_90: int = Field(
        default=90, description="Token usage threshold for 90% alert"
    )
    alert_token_threshold_95: int = Field(
        default=95, description="Token usage threshold for 95% alert"
    )
    alert_token_threshold_100: int = Field(
        default=100, description="Token usage threshold for 100% alert"
    )

    # Phase 4: PrivacyManager settings
    privacy_enabled: bool = Field(default=True, description="Enable privacy protection system")
    privacy_default_level: str = Field(
        default="medium", description="Default privacy level: none, low, medium, high"
    )
    privacy_masking_type: str = Field(
        default="asterisk", description="Default masking type: asterisk, partial, hash, remove"
    )
    privacy_pii_detection: bool = Field(default=True, description="Enable PII detection")
    privacy_api_key_detection: bool = Field(default=True, description="Enable API key detection")
    privacy_audit_enabled: bool = Field(default=True, description="Enable security audit logging")
    privacy_alert_integration: bool = Field(
        default=True, description="Integrate privacy events with AlertManager"
    )
    privacy_retention_days: int = Field(default=90, description="Privacy event retention days")

    @field_validator("discord_token")
    @classmethod
    def validate_discord_token(cls, v):
        """Validate Discord token format."""
        if not v:
            raise ValueError("Discord token is required")
        if not v.startswith(("Bot ", "MTA", "ODQ", "OTQ", "MT")):
            raise ValueError("Invalid Discord token format")
        return v

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v):
        """Validate OpenAI API key format."""
        if not v:
            raise ValueError("OpenAI API key is required")
        if not v.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            levels_str = ", ".join(valid_levels)
            raise ValueError(f"Log level must be one of: {levels_str}")
        return v.upper()

    @field_validator("max_audio_size_mb")
    @classmethod
    def validate_max_audio_size(cls, v):
        """Validate maximum audio file size."""
        if v <= 0:
            raise ValueError("Maximum audio size must be positive")
        if v > 100:
            raise ValueError("Maximum audio size should not exceed 100MB")
        return v

    @field_validator("speech_language")
    @classmethod
    def validate_speech_language(cls, v):
        """Validate speech language code."""
        # Common language codes
        valid_languages = ["ja", "en", "es", "fr", "de", "it", "pt", "ru", "ko", "zh"]
        if v not in valid_languages:
            # Allow any 2-letter language code, but warn about common ones
            if len(v) != 2:
                raise ValueError("Speech language should be a 2-letter language code")
        return v.lower()

    @field_validator("github_repo_owner")
    @classmethod
    def validate_github_repo_owner(cls, v):
        """Validate GitHub repository owner name."""
        if v is None:
            return v

        from .security import SecurityValidator

        try:
            return SecurityValidator.validate_github_owner_name(v)
        except ValueError as e:
            raise ValueError(f"Invalid GitHub repository owner: {e}")

    @field_validator("github_repo_name")
    @classmethod
    def validate_github_repo_name(cls, v):
        """Validate GitHub repository name."""
        if v is None:
            return v

        from .security import SecurityValidator

        try:
            return SecurityValidator.validate_github_repository_name(v)
        except ValueError as e:
            raise ValueError(f"Invalid GitHub repository name: {e}")

    @field_validator("github_obsidian_base_path")
    @classmethod
    def validate_github_obsidian_base_path(cls, v):
        """Validate GitHub Obsidian base path."""
        from .security import SecurityValidator

        try:
            return SecurityValidator.validate_file_path(v)
        except Exception as e:
            raise ValueError(f"Invalid GitHub Obsidian base path: {e}")

    @field_validator("github_obsidian_branch")
    @classmethod
    def validate_github_obsidian_branch(cls, v):
        """Validate GitHub branch name."""
        if not v:
            raise ValueError("GitHub branch name cannot be empty")

        # GitHub branch name validation
        if not re.match(r"^[a-zA-Z0-9._/-]{1,250}$", v):
            raise ValueError("Invalid GitHub branch name format")

        # Cannot start with dot, slash, or hyphen
        if v.startswith((".", "/", "-")):
            raise ValueError("Branch name cannot start with '.', '/', or '-'")

        return v

    @field_validator("github_obsidian_batch_size")
    @classmethod
    def validate_batch_size(cls, v):
        """Validate batch size."""
        if v <= 0:
            raise ValueError("Batch size must be positive")
        if v > 100:
            raise ValueError("Batch size should not exceed 100")
        return v

    @field_validator("github_obsidian_batch_interval")
    @classmethod
    def validate_batch_interval(cls, v):
        """Validate batch interval."""
        if v < 60:
            raise ValueError("Batch interval must be at least 60 seconds")
        if v > 3600:
            raise ValueError("Batch interval should not exceed 3600 seconds (1 hour)")
        return v

    @field_validator("max_file_size_kb")
    @classmethod
    def validate_max_file_size_kb(cls, v):
        """Validate maximum file size."""
        if v <= 0:
            raise ValueError("Maximum file size must be positive")
        if v > 10240:  # 10MB
            raise ValueError("Maximum file size should not exceed 10MB")
        return v

    # Phase 4: New validators
    @field_validator("gemini_api_key")
    @classmethod
    def validate_gemini_api_key(cls, v):
        """Validate Gemini API key format."""
        if v is None:
            return v
        if not isinstance(v, str) or len(v.strip()) == 0:
            raise ValueError("Gemini API key cannot be empty")
        # Gemini API keys typically start with specific patterns
        if not v.startswith(("AIza", "API-")):
            raise ValueError("Invalid Gemini API key format")
        return v

    @field_validator("gemini_monthly_limit")
    @classmethod
    def validate_gemini_monthly_limit(cls, v):
        """Validate Gemini monthly limit."""
        if v <= 0:
            raise ValueError("Gemini monthly limit must be positive")
        if v > 1000000:  # 1M tokens
            raise ValueError("Gemini monthly limit is too high")
        return v

    @field_validator("gemini_requests_per_minute")
    @classmethod
    def validate_gemini_requests_per_minute(cls, v):
        """Validate Gemini request rate limit."""
        if v <= 0:
            raise ValueError("Gemini requests per minute must be positive")
        if v > 60:
            raise ValueError("Gemini requests per minute should not exceed 60")
        return v

    @field_validator("chromadb_distance_metric")
    @classmethod
    def validate_chromadb_distance_metric(cls, v):
        """Validate ChromaDB distance metric."""
        valid_metrics = ["cosine", "l2", "ip"]
        if v not in valid_metrics:
            metrics_str = ", ".join(valid_metrics)
            raise ValueError(f"ChromaDB distance metric must be one of: {metrics_str}")
        return v

    @field_validator("chromadb_max_batch_size")
    @classmethod
    def validate_chromadb_max_batch_size(cls, v):
        """Validate ChromaDB maximum batch size."""
        if v <= 0:
            raise ValueError("ChromaDB maximum batch size must be positive")
        if v > 1000:
            raise ValueError("ChromaDB maximum batch size should not exceed 1000")
        return v

    @field_validator("hybrid_search_alpha")
    @classmethod
    def validate_hybrid_search_alpha(cls, v):
        """Validate hybrid search alpha parameter."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Hybrid search alpha must be between 0.0 and 1.0")
        return v

    @field_validator("max_search_results")
    @classmethod
    def validate_max_search_results(cls, v):
        """Validate maximum search results."""
        if v <= 0:
            raise ValueError("Maximum search results must be positive")
        if v > 100:
            raise ValueError("Maximum search results should not exceed 100")
        return v

    @field_validator("embedding_dimension")
    @classmethod
    def validate_embedding_dimension(cls, v):
        """Validate embedding dimension."""
        valid_dimensions = [256, 384, 512, 768, 1024, 1536, 3072]
        if v not in valid_dimensions:
            dimensions_str = ", ".join(map(str, valid_dimensions))
            raise ValueError(f"Embedding dimension must be one of: {dimensions_str}")
        return v

    @field_validator("ai_api_mode")
    @classmethod
    def validate_ai_api_mode(cls, v):
        """Validate AI API mode."""
        valid_modes = ["openai", "gemini", "hybrid"]
        if v not in valid_modes:
            modes_str = ", ".join(valid_modes)
            raise ValueError(f"AI API mode must be one of: {modes_str}")
        return v

    @field_validator("api_timeout_seconds")
    @classmethod
    def validate_api_timeout_seconds(cls, v):
        """Validate API timeout."""
        if v <= 0:
            raise ValueError("API timeout must be positive")
        if v > 300:  # 5 minutes
            raise ValueError("API timeout should not exceed 300 seconds")
        return v

    @field_validator("max_retry_attempts")
    @classmethod
    def validate_max_retry_attempts(cls, v):
        """Validate maximum retry attempts."""
        if v < 0:
            raise ValueError("Maximum retry attempts cannot be negative")
        if v > 10:
            raise ValueError("Maximum retry attempts should not exceed 10")
        return v

    # AlertManager validators
    @field_validator("alert_monitoring_interval")
    @classmethod
    def validate_alert_monitoring_interval(cls, v):
        """Validate alert monitoring interval."""
        if v < 60:
            raise ValueError("Alert monitoring interval must be at least 60 seconds")
        if v > 3600:
            raise ValueError("Alert monitoring interval should not exceed 3600 seconds")
        return v

    @field_validator("alert_default_cooldown")
    @classmethod
    def validate_alert_default_cooldown(cls, v):
        """Validate alert default cooldown."""
        if v < 1:
            raise ValueError("Alert default cooldown must be at least 1 minute")
        if v > 1440:  # 24 hours
            raise ValueError("Alert default cooldown should not exceed 1440 minutes (24 hours)")
        return v

    @field_validator("alert_max_history_size")
    @classmethod
    def validate_alert_max_history_size(cls, v):
        """Validate alert max history size."""
        if v < 10:
            raise ValueError("Alert max history size must be at least 10")
        if v > 1000:
            raise ValueError("Alert max history size should not exceed 1000")
        return v

    @field_validator("alert_memory_threshold_mb")
    @classmethod
    def validate_alert_memory_threshold_mb(cls, v):
        """Validate alert memory threshold."""
        if v < 100:
            raise ValueError("Alert memory threshold must be at least 100 MB")
        if v > 4096:  # 4GB
            raise ValueError("Alert memory threshold should not exceed 4096 MB")
        return v

    @field_validator("alert_token_threshold_90")
    @classmethod
    def validate_alert_token_threshold_90(cls, v):
        """Validate 90% token threshold."""
        if v < 50 or v > 100:
            raise ValueError("90% token threshold must be between 50 and 100")
        return v

    @field_validator("alert_token_threshold_95")
    @classmethod
    def validate_alert_token_threshold_95(cls, v):
        """Validate 95% token threshold."""
        if v < 50 or v > 100:
            raise ValueError("95% token threshold must be between 50 and 100")
        return v

    @field_validator("alert_token_threshold_100")
    @classmethod
    def validate_alert_token_threshold_100(cls, v):
        """Validate 100% token threshold."""
        if v < 50 or v > 100:
            raise ValueError("100% token threshold must be between 50 and 100")
        return v

    @model_validator(mode="after")
    def validate_github_integration(self):
        """Validate GitHub integration settings consistency."""
        if self.github_obsidian_enabled:
            if not self.github_token:
                raise ValueError(
                    "GitHub token is required when GitHub-Obsidian integration is enabled"
                )
            if not self.github_repo_owner:
                raise ValueError(
                    "GitHub repository owner is required when "
                    "GitHub-Obsidian integration is enabled"
                )
            if not self.github_repo_name:
                raise ValueError(
                    "GitHub repository name is required when "
                    "GitHub-Obsidian integration is enabled"
                )

        return self

    @model_validator(mode="after")
    def validate_phase4_settings(self):
        """Validate Phase 4 PKM feature settings consistency."""
        # PKM features require Gemini API when ai_api_mode is gemini or hybrid
        if self.pkm_enabled:
            if self.ai_api_mode in ["gemini", "hybrid"] and not self.gemini_api_key:
                raise ValueError(
                    "Gemini API key is required when PKM is enabled "
                    "and AI API mode is 'gemini' or 'hybrid'"
                )

            # ChromaDB persist directory must be accessible
            from pathlib import Path

            persist_path = Path(self.chromadb_persist_directory)
            if persist_path.is_file():
                raise ValueError(
                    f"ChromaDB persist directory '{self.chromadb_persist_directory}' "
                    "is a file, not a directory"
                )

        # API mode validation
        if self.ai_api_mode == "gemini" and not self.gemini_api_key:
            raise ValueError("Gemini API key is required when AI API mode is 'gemini'")

        if self.ai_api_mode == "hybrid":
            if not self.gemini_api_key:
                raise ValueError("Gemini API key is required when AI API mode is 'hybrid'")
            if not self.enable_api_fallback:
                raise ValueError(
                    "API fallback should be enabled when using hybrid API mode "
                    "for better reliability"
                )

        return self


class ConfigManager:
    """
    Configuration manager for the NescordBot application.

    Handles loading and validation of configuration from environment variables
    and .env files.
    """

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            env_file: Path to .env file. If None, looks for .env in current
                directory.
        """
        self._config: Optional[BotConfig] = None
        self._env_file = env_file or ".env"
        self._load_env()

    def _load_env(self) -> None:
        """Load environment variables from .env file if it exists."""
        env_path = Path(self._env_file)
        if env_path.exists():
            load_dotenv(env_path)

    @property
    def config(self) -> BotConfig:
        """
        Get validated configuration.

        Returns:
            BotConfig: Validated configuration instance

        Raises:
            ValidationError: If required configuration is missing or
                invalid
        """
        if self._config is None:
            self._config = BotConfig(
                # Required settings
                discord_token=os.getenv("DISCORD_TOKEN", ""),
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
                # Optional settings with defaults
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                max_audio_size_mb=int(os.getenv("MAX_AUDIO_SIZE_MB", "25")),
                speech_language=os.getenv("SPEECH_LANGUAGE", "ja"),
                database_url=os.getenv("DATABASE_URL", "sqlite:///data/nescordbot.db"),
                # GitHub integration settings
                github_token=os.getenv("GITHUB_TOKEN"),
                github_repo_owner=os.getenv("GITHUB_REPO_OWNER"),
                github_repo_name=os.getenv("GITHUB_REPO_NAME"),
                # Obsidian integration settings
                obsidian_vault_path=os.getenv("OBSIDIAN_VAULT_PATH"),
                # GitHub Obsidian integration settings
                github_obsidian_enabled=os.getenv("GITHUB_OBSIDIAN_ENABLED", "false").lower()
                == "true",
                github_obsidian_base_path=os.getenv("GITHUB_OBSIDIAN_BASE_PATH", "obsidian_sync"),
                github_obsidian_branch=os.getenv("GITHUB_OBSIDIAN_BRANCH", "main"),
                github_obsidian_batch_size=int(os.getenv("GITHUB_OBSIDIAN_BATCH_SIZE", "10")),
                github_obsidian_batch_interval=int(
                    os.getenv("GITHUB_OBSIDIAN_BATCH_INTERVAL", "300")
                ),
                # Instance management settings
                instance_id=os.getenv("INSTANCE_ID"),
                # Security settings
                max_file_size_kb=int(os.getenv("MAX_FILE_SIZE_KB", "1024")),
                enable_content_validation=os.getenv("ENABLE_CONTENT_VALIDATION", "true").lower()
                == "true",
                # Phase 4: Gemini API settings
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                gemini_monthly_limit=int(os.getenv("GEMINI_MONTHLY_LIMIT", "50000")),
                gemini_requests_per_minute=int(os.getenv("GEMINI_REQUESTS_PER_MINUTE", "15")),
                # Phase 4: ChromaDB settings
                chromadb_persist_directory=os.getenv("CHROMADB_PERSIST_DIRECTORY", "data/chromadb"),
                chromadb_collection_name=os.getenv("CHROMADB_COLLECTION_NAME", "nescord_knowledge"),
                chromadb_distance_metric=os.getenv("CHROMADB_DISTANCE_METRIC", "cosine"),
                chromadb_max_batch_size=int(os.getenv("CHROMADB_MAX_BATCH_SIZE", "100")),
                # Phase 4: PKM feature settings
                pkm_enabled=os.getenv("PKM_ENABLED", "false").lower() == "true",
                hybrid_search_enabled=os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true",
                hybrid_search_alpha=float(os.getenv("HYBRID_SEARCH_ALPHA", "0.7")),
                max_search_results=int(os.getenv("MAX_SEARCH_RESULTS", "10")),
                embedding_dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
                # Phase 4: Advanced RRF settings
                rrf_k_value=int(os.getenv("RRF_K_VALUE", "60")),
                enable_dynamic_rrf_k=os.getenv("ENABLE_DYNAMIC_RRF_K", "true").lower() == "true",
                search_cache_enabled=os.getenv("SEARCH_CACHE_ENABLED", "true").lower() == "true",
                search_cache_ttl_seconds=int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "300")),
                # Phase 4: API migration mode settings
                ai_api_mode=os.getenv("AI_API_MODE", "openai"),
                enable_api_fallback=os.getenv("ENABLE_API_FALLBACK", "true").lower() == "true",
                api_timeout_seconds=int(os.getenv("API_TIMEOUT_SECONDS", "30")),
                max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
                # Phase 4: AlertManager settings
                alert_enabled=os.getenv("ALERT_ENABLED", "true").lower() == "true",
                alert_channel_id=int(channel_id)
                if (channel_id := os.getenv("ALERT_CHANNEL_ID"))
                else None,
                alert_monitoring_interval=int(os.getenv("ALERT_MONITORING_INTERVAL", "300")),
                alert_default_cooldown=int(os.getenv("ALERT_DEFAULT_COOLDOWN", "30")),
                alert_max_history_size=int(os.getenv("ALERT_MAX_HISTORY_SIZE", "100")),
                alert_memory_threshold_mb=int(os.getenv("ALERT_MEMORY_THRESHOLD_MB", "500")),
                alert_token_threshold_90=int(os.getenv("ALERT_TOKEN_THRESHOLD_90", "90")),
                alert_token_threshold_95=int(os.getenv("ALERT_TOKEN_THRESHOLD_95", "95")),
                alert_token_threshold_100=int(os.getenv("ALERT_TOKEN_THRESHOLD_100", "100")),
                # Phase 4: PrivacyManager settings
                privacy_enabled=os.getenv("PRIVACY_ENABLED", "true").lower() == "true",
                privacy_default_level=os.getenv("PRIVACY_DEFAULT_LEVEL", "medium"),
                privacy_masking_type=os.getenv("PRIVACY_MASKING_TYPE", "asterisk"),
                privacy_pii_detection=os.getenv("PRIVACY_PII_DETECTION", "true").lower() == "true",
                privacy_api_key_detection=os.getenv("PRIVACY_API_KEY_DETECTION", "true").lower()
                == "true",
                privacy_audit_enabled=os.getenv("PRIVACY_AUDIT_ENABLED", "true").lower() == "true",
                privacy_alert_integration=os.getenv("PRIVACY_ALERT_INTEGRATION", "true").lower()
                == "true",
                privacy_retention_days=int(os.getenv("PRIVACY_RETENTION_DAYS", "90")),
            )
        return self._config

    def reload(self) -> None:
        """Reload configuration from environment variables."""
        self._config = None
        self._load_env()

    def validate_github_integration_setup(self) -> bool:
        """
        Validate that GitHub integration is properly configured.

        Returns:
            bool: True if GitHub integration is ready to use
        """
        config = self.config

        if not config.github_obsidian_enabled:
            return False

        required_fields = [
            config.github_token,
            config.github_repo_owner,
            config.github_repo_name,
        ]

        return all(field is not None and field.strip() for field in required_fields)

    def get_instance_id(self) -> str:
        """
        Get or generate unique instance identifier.

        Returns:
            str: Unique instance identifier
        """
        config = self.config

        if config.instance_id:
            return config.instance_id

        # Generate instance ID based on environment
        import hashlib
        import socket

        hostname = socket.gethostname()
        process_id = os.getpid()
        unique_string = f"{hostname}_{process_id}_{os.getenv('RAILWAY_DEPLOYMENT_ID', 'local')}"

        # Create short hash for instance ID
        instance_hash = hashlib.md5(unique_string.encode()).hexdigest()[:8]
        return f"nescord_{instance_hash}"

    # Existing getter methods
    def get_discord_token(self) -> str:
        """Get Discord bot token."""
        return self.config.discord_token

    def get_openai_api_key(self) -> str:
        """Get OpenAI API key."""
        return self.config.openai_api_key

    def get_log_level(self) -> str:
        """Get logging level."""
        return self.config.log_level

    def get_max_audio_size_mb(self) -> int:
        """Get maximum audio file size in MB."""
        return self.config.max_audio_size_mb

    def get_speech_language(self) -> str:
        """Get speech recognition language."""
        return self.config.speech_language

    def get_database_url(self) -> str:
        """Get database URL."""
        return self.config.database_url

    def get_github_token(self) -> Optional[str]:
        """Get GitHub API token."""
        return self.config.github_token

    def get_github_repo_owner(self) -> Optional[str]:
        """Get GitHub repository owner."""
        return self.config.github_repo_owner

    def get_github_repo_name(self) -> Optional[str]:
        """Get GitHub repository name."""
        return self.config.github_repo_name

    def get_obsidian_vault_path(self) -> Optional[str]:
        """Get Obsidian vault path."""
        return self.config.obsidian_vault_path

    # New getter methods for GitHub Obsidian integration
    def is_github_obsidian_enabled(self) -> bool:
        """Check if GitHub Obsidian integration is enabled."""
        return self.config.github_obsidian_enabled

    def get_github_obsidian_base_path(self) -> str:
        """Get GitHub Obsidian base path."""
        return self.config.github_obsidian_base_path

    def get_github_obsidian_branch(self) -> str:
        """Get GitHub Obsidian branch."""
        return self.config.github_obsidian_branch

    def get_github_obsidian_batch_size(self) -> int:
        """Get GitHub Obsidian batch size."""
        return self.config.github_obsidian_batch_size

    def get_github_obsidian_batch_interval(self) -> int:
        """Get GitHub Obsidian batch interval."""
        return self.config.github_obsidian_batch_interval

    def get_max_file_size_kb(self) -> int:
        """Get maximum file size in KB."""
        return self.config.max_file_size_kb

    def is_content_validation_enabled(self) -> bool:
        """Check if content validation is enabled."""
        return self.config.enable_content_validation


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get global configuration manager instance.

    Returns:
        ConfigManager: Global configuration manager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> BotConfig:
    """
    Get validated bot configuration.

    Returns:
        BotConfig: Validated configuration instance
    """
    return get_config_manager().config
