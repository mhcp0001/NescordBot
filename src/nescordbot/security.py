"""
Security validation module for NescordBot.

This module provides comprehensive security validation for user inputs,
file operations, and content processing to prevent XSS, injection attacks,
and path traversal vulnerabilities.
"""

import html
import logging
import re
import unicodedata
from typing import Any, Dict, List

from pathvalidate import sanitize_filename as pv_sanitize_filename

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Security-related errors."""

    pass


class SecurityValidator:
    """Comprehensive security validation for all user inputs and file operations."""

    # XSS attack patterns
    XSS_PATTERNS = [
        r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe\b[^>]*>",
        r"<object\b[^>]*>",
        r"<embed\b[^>]*>",
    ]

    # Code injection patterns
    INJECTION_PATTERNS = [
        r"(?i)\b(eval|exec|system|subprocess|os\.system)\s*\(",
        r"(?i)\b(import|from|__import__)\s+",
        r"\$\([^)]*\)",  # Command substitution
        r"`[^`]*`",  # Backtick command execution
    ]

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(?i)\b(select|insert|update|delete|drop|create|alter)\b",
        r"(?i)\b(union|or|and)\s+\d+\s*=\s*\d+",
        r'[\'"];?\s*(--|#)',
    ]

    @classmethod
    def validate_discord_content(cls, content: str) -> str:
        """
        Validate and sanitize Discord message content.

        Args:
            content: Raw Discord message content

        Returns:
            Sanitized content safe for processing

        Raises:
            ValueError: If content is invalid
            SecurityError: If malicious content is detected
        """
        if not content:
            raise ValueError("Content cannot be empty")

        # Length limit (10KB)
        if len(content) > 10000:
            raise ValueError("Content too large (max 10KB)")

        # XSS attack pattern detection
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning(f"XSS pattern detected in content: {pattern}")
                raise SecurityError("Potentially malicious content detected")

        # Code injection attack detection
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning(f"Code injection pattern detected: {pattern}")
                raise SecurityError("Potentially malicious code detected")

        # HTML escape for safety
        escaped_content = html.escape(content)

        # Unicode normalization
        normalized_content = unicodedata.normalize("NFKC", escaped_content)

        return normalized_content

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Strictly sanitize filename to prevent path traversal and file system issues.

        Args:
            filename: Raw filename

        Returns:
            Sanitized filename safe for filesystem operations

        Raises:
            ValueError: If filename is invalid
        """
        if not filename:
            raise ValueError("Filename cannot be empty")

        # Use pathvalidate for basic sanitization
        sanitized = pv_sanitize_filename(filename, replacement_text="_")

        # Additional security measures

        # Remove consecutive dots (path traversal prevention)
        sanitized = re.sub(r"\.{2,}", ".", sanitized)

        # Strip dangerous leading/trailing characters
        sanitized = sanitized.strip(". ")

        # Windows reserved names check
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ]

        name_without_ext = sanitized.split(".")[0].upper()
        if name_without_ext in reserved_names:
            sanitized = f"file_{sanitized}"

        # Length limit (200 chars)
        if len(sanitized) > 200:
            name_part = sanitized[:190]
            ext_part = sanitized[-10:] if "." in sanitized else ""
            sanitized = f"{name_part}...{ext_part}"

        # Ensure we have a valid filename
        if not sanitized or sanitized in [".", ".."]:
            sanitized = f"sanitized_file_{hash(filename) % 10000}.txt"

        return str(sanitized)

    @classmethod
    def validate_yaml_frontmatter(cls, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize YAML frontmatter content.

        Args:
            frontmatter: Raw frontmatter dictionary

        Returns:
            Sanitized frontmatter dictionary
        """
        validated: Dict[str, Any] = {}

        for key, value in frontmatter.items():
            # Key name validation (alphanumeric, underscore, hyphen only)
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", key):
                logger.warning(f"Invalid frontmatter key: {key}")
                continue

            # Value validation and sanitization
            if isinstance(value, str):
                # String value validation
                sanitized_value = value
                if len(sanitized_value) > 1000:
                    sanitized_value = sanitized_value[:997] + "..."

                # Dangerous pattern detection
                for pattern in cls.INJECTION_PATTERNS:
                    if re.search(pattern, sanitized_value, re.IGNORECASE):
                        logger.warning(f"Dangerous pattern in frontmatter value: {key}")
                        sanitized_value = "[SANITIZED]"
                        break

                validated[key] = html.escape(sanitized_value)

            elif isinstance(value, (int, float, bool)):
                validated[key] = value

            elif isinstance(value, list):
                # Validate list elements
                validated_list: List[str] = []
                for item in value[:50]:  # List size limit
                    if isinstance(item, str) and len(item) < 100:
                        validated_list.append(html.escape(item))
                validated[key] = validated_list

            else:
                logger.warning(f"Unsupported frontmatter value type: {type(value)}")

        return validated

    @classmethod
    def validate_file_path(cls, file_path: str) -> str:
        """
        Validate file path to prevent path traversal attacks.

        Args:
            file_path: Raw file path

        Returns:
            Validated and normalized file path

        Raises:
            SecurityError: If path contains dangerous patterns
        """
        if not file_path:
            raise ValueError("File path cannot be empty")

        # Normalize path separators
        normalized_path = file_path.replace("\\", "/").strip()

        # Check for path traversal patterns
        dangerous_patterns = ["../", "..\\", "~/", "/etc/", "/proc/", "/sys/"]
        for pattern in dangerous_patterns:
            if pattern in normalized_path.lower():
                raise SecurityError(f"Potentially dangerous path pattern: {pattern}")

        # Check for absolute paths (should be relative)
        if normalized_path.startswith("/") or (
            len(normalized_path) > 1 and normalized_path[1] == ":"
        ):
            raise SecurityError("Absolute paths are not allowed")

        # Sanitize path components
        path_parts = normalized_path.split("/")
        sanitized_parts = []

        for part in path_parts:
            if part in [".", ".."]:
                continue  # Skip dangerous components
            if part:  # Skip empty parts
                sanitized_part = cls.sanitize_filename(part)
                sanitized_parts.append(sanitized_part)

        return "/".join(sanitized_parts)

    @classmethod
    def validate_github_repository_name(cls, repo_name: str) -> str:
        """
        Validate GitHub repository name format.

        Args:
            repo_name: Repository name

        Returns:
            Validated repository name

        Raises:
            ValueError: If repository name is invalid
        """
        if not repo_name:
            raise ValueError("Repository name cannot be empty")

        # GitHub repository name validation
        # Must be 1-100 characters, contain only alphanumeric, hyphens, underscores, dots
        if not re.match(r"^[a-zA-Z0-9._-]{1,100}$", repo_name):
            raise ValueError("Invalid repository name format")

        # Cannot start or end with special characters
        if repo_name.startswith((".", "-", "_")) or repo_name.endswith((".", "-", "_")):
            raise ValueError("Repository name cannot start or end with special characters")

        return repo_name

    @classmethod
    def validate_github_owner_name(cls, owner_name: str) -> str:
        """
        Validate GitHub owner/organization name format.

        Args:
            owner_name: Owner or organization name

        Returns:
            Validated owner name

        Raises:
            ValueError: If owner name is invalid
        """
        if not owner_name:
            raise ValueError("Owner name cannot be empty")

        # GitHub username validation
        # Must be 1-39 characters, contain only alphanumeric and hyphens
        if not re.match(r"^[a-zA-Z0-9-]{1,39}$", owner_name):
            raise ValueError("Invalid GitHub owner name format")

        # Cannot start or end with hyphen
        if owner_name.startswith("-") or owner_name.endswith("-"):
            raise ValueError("Owner name cannot start or end with hyphen")

        # Cannot contain consecutive hyphens
        if "--" in owner_name:
            raise ValueError("Owner name cannot contain consecutive hyphens")

        return owner_name
