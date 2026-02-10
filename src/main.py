#!/usr/bin/env python3
"""
WordPress → PrestaShop Migration Tool
CLI entry point.

Usage:
    python -m src --interactive                              # Interactive wizard
    python -m src --interactive --url https://example.com    # Wizard with pre-set URL
    python -m src --config config.yaml --dry-run             # Automated dry-run
    python -m src --config config.yaml                       # Automated live migration
"""

import argparse
import sys

from .config import load_config
from .migrator import Migrator
from .utils import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate content from WordPress to PrestaShop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Modes:
  Interactive:    %(prog)s --interactive --url https://www.example.com
  Automated:      %(prog)s --config config.yaml --dry-run
  Preview only:   python -m src.preview --url https://www.example.com
        """,
    )

    # Mode selection
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Launch interactive wizard: scan, choose destinations, then migrate",
    )
    parser.add_argument(
        "--url", "-u",
        default=None,
        help="WordPress URL (for interactive mode)",
    )

    # Automated mode
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview mode: fetch and transform but do not write to PrestaShop",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # ── Interactive mode ─────────────────────────────────────────
    if args.interactive:
        from .interactive import run_interactive
        run_interactive(wp_url=args.url, config_path=args.config)
        return 0

    # ── Automated mode ───────────────────────────────────────────
    config = load_config(args.config)

    if args.dry_run:
        config.migration.dry_run = True

    logger = setup_logging(
        log_file=config.migration.log_file,
        verbose=args.verbose,
    )

    logger.info("WordPress → PrestaShop Migration Tool v2.0")
    logger.info(f"Config: {args.config}")

    if config.migration.dry_run:
        logger.info("🔍 DRY RUN MODE — no changes will be made to PrestaShop")

    try:
        migrator = Migrator(config)
        migrator.run()
        return 0
    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user.")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
