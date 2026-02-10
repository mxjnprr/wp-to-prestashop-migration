"""
Migration orchestrator.
Coordinates the ETL pipeline: Extract (WP) → Transform → Load (PrestaShop).
"""

import logging
import os
import shutil
from typing import Any

from .config import AppConfig
from .wp_client import WordPressClient
from .ps_client import PrestaShopClient
from .transformers import ContentTransformer
from .utils import format_summary

logger = logging.getLogger("wp2presta")


class Migrator:
    """Orchestrates the WordPress → PrestaShop content migration."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.dry_run = config.migration.dry_run

        # Initialize clients
        self.wp = WordPressClient(
            api_base=config.wordpress.api_base,
            username=config.wordpress.username,
            app_password=config.wordpress.app_password,
        )
        self.ps = PrestaShopClient(
            api_base=config.prestashop.api_base,
            api_key=config.prestashop.api_key,
            default_lang_id=config.prestashop.default_lang_id,
        )
        self.transformer = ContentTransformer(
            wp_base_url=config.wordpress.url,
            ps_base_url=config.prestashop.url,
            image_temp_dir=config.migration.image_temp_dir,
        )

        # Counters
        self.stats = {
            "migrated": 0,
            "failed": 0,
            "skipped": 0,
            "images": 0,
        }

    def run(self) -> None:
        """Execute the full migration pipeline."""
        logger.info("=" * 60)
        logger.info("  WordPress → PrestaShop Migration")
        logger.info(f"  WP:    {self.config.wordpress.url}")
        logger.info(f"  PS:    {self.config.prestashop.url}")
        logger.info(f"  Mode:  {'🔍 DRY RUN' if self.dry_run else '🚀 LIVE'}")
        logger.info("=" * 60)

        # Step 0: Test PrestaShop connection
        if not self.dry_run:
            if not self.ps.test_connection():
                logger.error("Cannot connect to PrestaShop API. Aborting.")
                return

        # Step 1: Prepare temp directory for images
        if self.config.migration.download_images:
            os.makedirs(self.config.migration.image_temp_dir, exist_ok=True)

        # Step 2: Fetch all WordPress pages
        logger.info("━" * 40)
        logger.info("Phase 1: Extracting WordPress pages...")
        wp_pages = self.wp.get_pages()

        if not wp_pages:
            logger.warning("No pages found on WordPress. Nothing to migrate.")
            return

        # Step 3: Process each page
        logger.info("━" * 40)
        logger.info("Phase 2: Transforming and loading pages...")

        for i, wp_page in enumerate(wp_pages, 1):
            page_data = self.wp.extract_page_data(wp_page)
            title = page_data.get("title", "(untitled)")
            slug = page_data.get("slug", "")

            logger.info(f"[{i}/{len(wp_pages)}] Processing: {title} (/{slug})")

            try:
                self._migrate_single_page(page_data)
            except Exception as e:
                logger.error(f"  ❌ Unexpected error: {e}")
                self.stats["failed"] += 1

        # Step 4: Summary
        summary = format_summary(
            migrated=self.stats["migrated"],
            failed=self.stats["failed"],
            skipped=self.stats["skipped"],
            images=self.stats["images"],
        )
        logger.info(summary)

        # Cleanup temp images
        if os.path.exists(self.config.migration.image_temp_dir):
            shutil.rmtree(self.config.migration.image_temp_dir, ignore_errors=True)
            logger.debug("Cleaned up temp image directory.")

    def _migrate_single_page(self, page_data: dict[str, Any]) -> None:
        """Process and migrate a single page."""
        slug = page_data.get("slug", "")
        title = page_data.get("title", "(untitled)")

        # Transform content
        self.transformer.reset_images()
        transformed = self.transformer.transform_page(page_data)

        # Handle images
        if self.config.migration.download_images:
            images = self.transformer.get_discovered_images()
            if images:
                logger.info(f"  🖼️  Found {len(images)} image(s) in content")
                self._handle_images(images)

        if self.dry_run:
            logger.info(f"  🔍 [DRY RUN] Would migrate: {title}")
            logger.info(f"     Slug: {transformed['slug']}")
            logger.info(f"     Meta title: {transformed['meta_title'][:80]}")
            logger.info(f"     Meta desc: {transformed['meta_description'][:80]}")
            logger.info(f"     Content length: {len(transformed['content'])} chars")
            self.stats["migrated"] += 1
            return

        # Check if page already exists (idempotency)
        existing_id = self.ps.find_cms_page_by_slug(transformed["slug"])

        if existing_id:
            logger.info(f"  🔄 Page exists (ID {existing_id}), updating...")
            success = self.ps.update_cms_page(
                page_id=existing_id,
                page_data=transformed,
                cms_category_id=self.config.prestashop.cms_category_id,
            )
        else:
            logger.info(f"  ✨ Creating new CMS page...")
            new_id = self.ps.create_cms_page(
                page_data=transformed,
                cms_category_id=self.config.prestashop.cms_category_id,
            )
            success = new_id is not None

        if success:
            self.stats["migrated"] += 1
            logger.info(f"  ✅ {title}")
        else:
            self.stats["failed"] += 1
            logger.error(f"  ❌ Failed: {title}")

    def _handle_images(self, images: list[dict[str, str]]) -> None:
        """Download images from WordPress and place them for PrestaShop."""
        target_dir = self.config.migration.image_target_dir
        temp_dir = self.config.migration.image_temp_dir

        for img_info in images:
            original_url = img_info["original_url"]
            filename = img_info["filename"]

            if self.dry_run:
                logger.info(f"    🔍 [DRY RUN] Would download: {filename}")
                self.stats["images"] += 1
                continue

            # Download
            image_data = self.wp.download_image(original_url)
            if not image_data:
                logger.warning(f"    ⚠️ Could not download: {filename}")
                continue

            # Save locally (always, for reference)
            local_path = os.path.join(temp_dir, filename)
            with open(local_path, "wb") as f:
                f.write(image_data)

            # If target directory specified, copy there
            if target_dir:
                dest_path = os.path.join(target_dir, filename)
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.copy2(local_path, dest_path)
                    logger.info(f"    📁 Copied: {filename} → {dest_path}")
                except (OSError, shutil.Error) as e:
                    logger.warning(f"    ⚠️ Could not copy {filename} to target: {e}")
            else:
                logger.info(f"    💾 Downloaded: {filename} (in {temp_dir}/)")
                logger.info(f"       ℹ️ Set migration.image_target_dir to auto-deploy images")

            self.stats["images"] += 1
