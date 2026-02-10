#!/usr/bin/env python3
"""
WordPress → PrestaShop Migration Tool
CLI entry point.

Usage:
    python -m src.main --config config.yaml
    python -m src.main --config config.yaml --dry-run
    python -m src.main --config config.yaml --dry-run --verbose
"""

import argparse
import sys

from .config import load_config
from .migrator import Migrator
from .utils import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate content from WordPress to PrestaShop (CMS pages, images, SEO metadata).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --config config.yaml --dry-run      Preview migration without changes
  %(prog)s --config config.yaml                 Run the migration
  %(prog)s --config config.yaml --verbose       Run with debug logging
        """,
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview mode: fetch and transform data but do not write to PrestaShop",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Load configuration
    config = load_config(args.config)

    # Override dry-run from CLI if specified
    if args.dry_run:
        config.migration.dry_run = True

    # Setup logging
    logger = setup_logging(
        log_file=config.migration.log_file,
        verbose=args.verbose,
    )

    logger.info("WordPress → PrestaShop Migration Tool v1.0")
    logger.info(f"Config: {args.config}")

    if config.migration.dry_run:
        logger.info("🔍 DRY RUN MODE — no changes will be made to PrestaShop")

    # Run migration
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
