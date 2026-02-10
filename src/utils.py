"""
Utility functions: logging setup, HTML helpers, slug sanitization.
"""

import logging
import re
import html
import unicodedata
from typing import Optional


def setup_logging(log_file: str, verbose: bool = False) -> logging.Logger:
    """Configure logging to both console and file."""
    logger = logging.getLogger("wp2presta")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", datefmt="%H:%M:%S")
    console_handler.setFormatter(console_fmt)

    # File handler
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def decode_html_entities(text: str) -> str:
    """Decode HTML entities in a string (e.g., &amp; → &, &#8217; → ')."""
    if not text:
        return ""
    return html.unescape(text)


def strip_html_tags(text: str) -> str:
    """Remove all HTML tags from a string, keeping text content."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def sanitize_slug(slug: str) -> str:
    """
    Sanitize a slug for PrestaShop's link_rewrite field.
    PrestaShop requires: lowercase, alphanumeric + hyphens only, no leading/trailing hyphens.
    """
    if not slug:
        return ""
    # NFD normalize, strip accents
    slug = unicodedata.normalize("NFD", slug)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    slug = slug.lower()
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug


def truncate(text: str, max_length: int = 255) -> str:
    """Truncate text to max_length, respecting word boundaries."""
    if not text or len(text) <= max_length:
        return text or ""
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated


def format_summary(migrated: int, failed: int, skipped: int, images: int) -> str:
    """Format a human-readable migration summary."""
    lines = [
        "═" * 50,
        "  MIGRATION SUMMARY",
        "═" * 50,
        f"  ✅ Pages migrated:  {migrated}",
        f"  ❌ Pages failed:    {failed}",
        f"  ⏭️  Pages skipped:   {skipped}",
        f"  🖼️  Images handled:  {images}",
        "═" * 50,
    ]
    return "\n".join(lines)
