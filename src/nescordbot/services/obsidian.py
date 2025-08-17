"""Obsidian integration service for NescordBot."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import discord

from ..config import BotConfig

logger = logging.getLogger(__name__)


class ObsidianFormatter:
    """Formatter for converting Discord content to Obsidian-compatible markdown."""

    @staticmethod
    def format_user_mention(user: discord.User | discord.Member) -> str:
        """Format Discord user mention for Obsidian.

        Args:
            user: Discord user or member

        Returns:
            Formatted user mention
        """
        return f"@{user.display_name} ({user.id})"

    @staticmethod
    def format_channel_mention(channel: discord.abc.GuildChannel | discord.Thread) -> str:
        """Format Discord channel mention for Obsidian.

        Args:
            channel: Discord channel or thread

        Returns:
            Formatted channel mention
        """
        return f"#{channel.name}"

    @staticmethod
    def format_timestamp(timestamp: datetime) -> str:
        """Format timestamp for Obsidian.

        Args:
            timestamp: Datetime object

        Returns:
            Formatted timestamp string
        """
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def format_embed(embed: discord.Embed) -> str:
        """Convert Discord embed to Obsidian markdown.

        Args:
            embed: Discord embed object

        Returns:
            Markdown formatted string
        """
        lines = []

        if embed.title:
            lines.append(f"### {embed.title}")
            lines.append("")

        if embed.description:
            lines.append(embed.description)
            lines.append("")

        for field in embed.fields:
            lines.append(f"**{field.name}**")
            lines.append(str(field.value))
            lines.append("")

        if embed.footer and embed.footer.text:
            lines.append(f"---\n*{embed.footer.text}*")

        return "\n".join(lines)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for filesystem.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem
        """
        # Remove or replace invalid characters
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, "_", filename)

        # Limit length
        max_length = 200
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        # Remove trailing dots and spaces
        sanitized = sanitized.rstrip(". ")

        return sanitized or "untitled"


class ObsidianService:
    """Service for managing Obsidian vault integration."""

    def __init__(self, config: BotConfig) -> None:
        """Initialize Obsidian service.

        Args:
            config: Application configuration
        """
        self.config = config
        self.vault_path = Path(config.obsidian_vault_path) if config.obsidian_vault_path else None
        self.formatter = ObsidianFormatter()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized and ready."""
        return self._initialized and self.vault_path is not None

    async def initialize(self) -> None:
        """Initialize the Obsidian service."""
        if not self.vault_path:
            logger.warning("Obsidian vault path not configured")
            return

        try:
            # Create vault directory if it doesn't exist
            self.vault_path.mkdir(parents=True, exist_ok=True)

            # Create subdirectories for different content types
            subdirs = ["messages", "voice", "github", "daily", "attachments"]
            for subdir in subdirs:
                (self.vault_path / subdir).mkdir(exist_ok=True)

            self._initialized = True
            logger.info(f"Obsidian service initialized with vault: {self.vault_path}")

        except Exception as e:
            logger.error(f"Failed to initialize Obsidian service: {e}")
            raise

    async def save_message(
        self,
        message: discord.Message,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder: str = "messages",
    ) -> Path:
        """Save Discord message to Obsidian vault.

        Args:
            message: Discord message to save
            title: Optional custom title
            tags: Optional list of tags
            folder: Folder within vault to save to

        Returns:
            Path to saved file

        Raises:
            RuntimeError: If service is not initialized
        """
        if not self.is_initialized or not self.vault_path:
            raise RuntimeError("Obsidian service is not initialized")

        # Generate filename
        timestamp = message.created_at.strftime("%Y%m%d_%H%M%S")
        author_name = self.formatter.sanitize_filename(message.author.display_name)
        default_title = f"{timestamp}_{author_name}"
        filename = self.formatter.sanitize_filename(title or default_title) + ".md"

        # Build file path
        file_path = self.vault_path / folder / filename

        # Build content
        content = await self._build_message_content(message, tags)

        # Save file
        await self._save_file(file_path, content)

        logger.info(f"Saved message to Obsidian: {file_path}")
        return file_path

    async def save_voice_transcription(
        self,
        transcription: str,
        user: discord.User | discord.Member,
        channel: discord.TextChannel | discord.Thread,
        duration: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> Path:
        """Save voice transcription to Obsidian vault.

        Args:
            transcription: Transcribed text
            user: User who sent the voice message
            channel: Channel where message was sent
            duration: Duration of voice message in seconds
            tags: Optional list of tags

        Returns:
            Path to saved file
        """
        if not self.is_initialized or not self.vault_path:
            raise RuntimeError("Obsidian service is not initialized")

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        username = self.formatter.sanitize_filename(user.display_name)
        filename = f"{timestamp}_voice_{username}.md"

        # Build file path
        file_path = self.vault_path / "voice" / filename

        # Build content
        content = self._build_voice_content(transcription, user, channel, duration, tags)

        # Save file
        await self._save_file(file_path, content)

        logger.info(f"Saved voice transcription to Obsidian: {file_path}")
        return file_path

    async def save_github_issue(
        self,
        issue_data: Dict[str, Any],
        tags: Optional[List[str]] = None,
    ) -> Path:
        """Save GitHub issue to Obsidian vault.

        Args:
            issue_data: GitHub issue data
            tags: Optional list of tags

        Returns:
            Path to saved file
        """
        if not self.is_initialized or not self.vault_path:
            raise RuntimeError("Obsidian service is not initialized")

        # Generate filename
        issue_number = issue_data.get("number", "unknown")
        title = self.formatter.sanitize_filename(issue_data.get("title", "untitled"))
        filename = f"issue_{issue_number}_{title}.md"

        # Build file path
        file_path = self.vault_path / "github" / filename

        # Build content
        content = self._build_github_issue_content(issue_data, tags)

        # Save file
        await self._save_file(file_path, content)

        logger.info(f"Saved GitHub issue to Obsidian: {file_path}")
        return file_path

    async def create_daily_note(
        self,
        date: Optional[datetime] = None,
        content: Optional[str] = None,
    ) -> Path:
        """Create or append to daily note.

        Args:
            date: Date for the note (defaults to today)
            content: Content to append

        Returns:
            Path to daily note file
        """
        if not self.is_initialized or not self.vault_path:
            raise RuntimeError("Obsidian service is not initialized")

        # Use today if no date provided
        if date is None:
            date = datetime.now()

        # Generate filename
        filename = date.strftime("%Y-%m-%d") + ".md"
        file_path = self.vault_path / "daily" / filename

        # Check if file exists
        if file_path.exists():
            # Append to existing file
            if content:
                async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
                    await f.write(f"\n\n---\n\n{content}")
        else:
            # Create new file
            daily_content = self._build_daily_note_template(date)
            if content:
                daily_content += f"\n\n## Notes\n\n{content}"
            await self._save_file(file_path, daily_content)

        logger.info(f"Created/updated daily note: {file_path}")
        return file_path

    async def save_attachment(
        self,
        attachment: discord.Attachment,
        related_note: Optional[Path] = None,
    ) -> Path:
        """Save Discord attachment to vault.

        Args:
            attachment: Discord attachment
            related_note: Path to related note file

        Returns:
            Path to saved attachment
        """
        if not self.is_initialized or not self.vault_path:
            raise RuntimeError("Obsidian service is not initialized")

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self.formatter.sanitize_filename(attachment.filename)}"
        file_path = self.vault_path / "attachments" / filename

        # Download and save attachment
        attachment_data = await attachment.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(attachment_data)

        # Update related note if provided
        if related_note and related_note.exists():
            async with aiofiles.open(related_note, "a", encoding="utf-8") as f:
                await f.write(f"\n\n![[{filename}]]\n")

        logger.info(f"Saved attachment to Obsidian: {file_path}")
        return file_path

    async def search_notes(
        self,
        query: str,
        folder: Optional[str] = None,
        limit: int = 10,
    ) -> List[Tuple[Path, str]]:
        """Search notes in vault.

        Args:
            query: Search query
            folder: Optional folder to search in
            limit: Maximum number of results

        Returns:
            List of (path, excerpt) tuples
        """
        if not self.is_initialized or not self.vault_path:
            raise RuntimeError("Obsidian service is not initialized")

        results: List[Tuple[Path, str]] = []
        search_path = self.vault_path / folder if folder else self.vault_path

        # Simple file content search
        for file_path in search_path.rglob("*.md"):
            if len(results) >= limit:
                break

            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    if query.lower() in content.lower():
                        # Extract excerpt around match
                        excerpt = self._extract_excerpt(content, query)
                        results.append((file_path, excerpt))
            except Exception as e:
                logger.debug(f"Error searching file {file_path}: {e}")

        return results

    # Private helper methods

    async def _build_message_content(
        self,
        message: discord.Message,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Build markdown content for Discord message."""
        lines = []

        # Frontmatter
        lines.append("---")
        lines.append(f"created: {self.formatter.format_timestamp(message.created_at)}")
        lines.append(f"author: {self.formatter.format_user_mention(message.author)}")
        lines.append(f"channel: {self.formatter.format_channel_mention(message.channel)}")  # type: ignore[arg-type]
        lines.append(f"message_id: {message.id}")

        if tags:
            lines.append(f"tags: [{', '.join(tags)}]")

        lines.append("---")
        lines.append("")

        # Main content
        lines.append("# Discord Message")
        lines.append("")

        # Message content
        if message.content:
            lines.append("## Content")
            lines.append(message.content)
            lines.append("")

        # Embeds
        if message.embeds:
            lines.append("## Embeds")
            for embed in message.embeds:
                lines.append(self.formatter.format_embed(embed))
                lines.append("")

        # Attachments
        if message.attachments:
            lines.append("## Attachments")
            for attachment in message.attachments:
                lines.append(f"- [{attachment.filename}]({attachment.url})")
            lines.append("")

        # Reactions
        if message.reactions:
            lines.append("## Reactions")
            for reaction in message.reactions:
                lines.append(f"- {reaction.emoji}: {reaction.count}")
            lines.append("")

        return "\n".join(lines)

    def _build_voice_content(
        self,
        transcription: str,
        user: discord.User | discord.Member,
        channel: discord.TextChannel | discord.Thread,
        duration: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Build markdown content for voice transcription."""
        lines = []

        # Frontmatter
        lines.append("---")
        lines.append(f"created: {self.formatter.format_timestamp(datetime.now())}")
        lines.append("type: voice_transcription")
        lines.append(f"author: {self.formatter.format_user_mention(user)}")
        lines.append(f"channel: {self.formatter.format_channel_mention(channel)}")

        if duration:
            lines.append(f"duration: {duration:.1f}s")

        if tags:
            lines.append(f"tags: [{', '.join(tags)}]")

        lines.append("---")
        lines.append("")

        # Main content
        lines.append("# Voice Transcription")
        lines.append("")
        lines.append("## Transcribed Text")
        lines.append(transcription)
        lines.append("")

        # Metadata
        lines.append("## Metadata")
        lines.append(f"- **Speaker**: {user.display_name}")
        lines.append(f"- **Channel**: #{channel.name}")
        lines.append(f"- **Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if duration:
            lines.append(f"- **Duration**: {duration:.1f} seconds")

        return "\n".join(lines)

    def _build_github_issue_content(
        self,
        issue_data: Dict[str, Any],
        tags: Optional[List[str]] = None,
    ) -> str:
        """Build markdown content for GitHub issue."""
        lines = []

        # Frontmatter
        lines.append("---")
        lines.append(f"created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("type: github_issue")
        lines.append(f"issue_number: {issue_data.get('number', 'unknown')}")
        lines.append(f"state: {issue_data.get('state', 'unknown')}")

        labels = issue_data.get("labels", [])
        if labels:
            label_names = [label.get("name", "") for label in labels]
            lines.append(f"labels: [{', '.join(label_names)}]")

        if tags:
            lines.append(f"tags: [{', '.join(tags)}]")

        lines.append("---")
        lines.append("")

        # Main content
        lines.append(f"# {issue_data.get('title', 'Untitled Issue')}")
        lines.append("")
        issue_num = issue_data.get("number", "unknown")
        issue_state = issue_data.get("state", "unknown").upper()
        lines.append(f"Issue #{issue_num} - {issue_state}")
        lines.append("")

        # Issue body
        if issue_data.get("body"):
            lines.append("## Description")
            lines.append(issue_data["body"])
            lines.append("")

        # Metadata
        lines.append("## Metadata")
        lines.append(f"- **URL**: {issue_data.get('html_url', 'N/A')}")
        lines.append(f"- **Created**: {issue_data.get('created_at', 'unknown')}")
        lines.append(f"- **Updated**: {issue_data.get('updated_at', 'unknown')}")

        if issue_data.get("user"):
            lines.append(f"- **Author**: @{issue_data['user'].get('login', 'unknown')}")

        if issue_data.get("assignees"):
            assignees = [f"@{a.get('login', '')}" for a in issue_data["assignees"]]
            lines.append(f"- **Assignees**: {', '.join(assignees)}")

        return "\n".join(lines)

    def _build_daily_note_template(self, date: datetime) -> str:
        """Build template for daily note."""
        lines = []

        # Frontmatter
        lines.append("---")
        lines.append(f"created: {date.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("type: daily_note")
        lines.append(f"date: {date.strftime('%Y-%m-%d')}")
        lines.append("---")
        lines.append("")

        # Title
        lines.append(f"# {date.strftime('%Y-%m-%d (%A)')}")
        lines.append("")

        # Sections
        lines.append("## Tasks")
        lines.append("- [ ] ")
        lines.append("")

        lines.append("## Discord Activity")
        lines.append("")

        lines.append("## GitHub Activity")
        lines.append("")

        return "\n".join(lines)

    async def _save_file(self, file_path: Path, content: str) -> None:
        """Save content to file."""
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

    def _extract_excerpt(self, content: str, query: str, context: int = 100) -> str:
        """Extract excerpt around search match."""
        lower_content = content.lower()
        lower_query = query.lower()

        pos = lower_content.find(lower_query)
        if pos == -1:
            return ""

        start = max(0, pos - context)
        end = min(len(content), pos + len(query) + context)

        excerpt = content[start:end]

        # Add ellipsis if truncated
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(content):
            excerpt = excerpt + "..."

        return excerpt
