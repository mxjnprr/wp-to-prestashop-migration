"""
Migration orchestrator.
Coordinates the ETL pipeline: Extract (WP) → Transform → Load (PrestaShop).
Supports three targets: CMS page, product description, or skip.
"""

import html
import logging
import os
import shutil
from typing import Any

from .config import AppConfig
from .wp_client import WordPressClient
from .ps_client import PrestaShopClient
from .transformers import ContentTransformer
from .router import MigrationRouter, RouteResult, build_router_from_config
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

        # Build router from mapping config
        self.router = build_router_from_config({
            "rules": config.mapping.rules,
            "default": config.mapping.default,
        })

        # Counters
        self.stats = {
            "cms_migrated": 0,
            "product_updated": 0,
            "skipped": 0,
            "failed": 0,
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

        # Router summary
        summary = self.router.get_summary()
        logger.info(
            f"  Router: {summary['total_rules']} rules "
            f"(CMS: {summary['cms_rules']}, Product: {summary['product_rules']}, "
            f"Skip: {summary['skip_rules']}), default: {summary['default']}"
        )

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

        # Step 3: Route and process each page
        logger.info("━" * 40)
        logger.info("Phase 2: Routing, transforming and loading pages...")

        for i, wp_page in enumerate(wp_pages, 1):
            page_data = self.wp.extract_page_data(wp_page)
            title = page_data.get("title", "(untitled)")
            slug = page_data.get("slug", "")

            # Route this page
            route = self.router.route(slug, title)
            logger.info(
                f"[{i}/{len(wp_pages)}] {title} (/{slug}) "
                f"→ {route.target.upper()} [{route.rule_name}]"
            )

            if route.target == "skip":
                self.stats["skipped"] += 1
                continue

            try:
                if route.target == "cms":
                    self._migrate_as_cms(page_data, route)
                elif route.target == "product":
                    self._migrate_as_product(page_data, route)
            except Exception as e:
                logger.error(f"  ❌ Unexpected error: {e}")
                self.stats["failed"] += 1

        # Step 4: Summary
        logger.info("━" * 40)
        logger.info("  RÉSUMÉ DE LA MIGRATION")
        logger.info("━" * 40)
        logger.info(f"  📄 Pages CMS migrées:    {self.stats['cms_migrated']}")
        logger.info(f"  🏷️  Produits mis à jour:  {self.stats['product_updated']}")
        logger.info(f"  ⏭️  Pages ignorées:       {self.stats['skipped']}")
        logger.info(f"  ❌ Échecs:                {self.stats['failed']}")
        logger.info(f"  🖼️  Images traitées:      {self.stats['images']}")

        # Cleanup temp images
        if os.path.exists(self.config.migration.image_temp_dir):
            shutil.rmtree(self.config.migration.image_temp_dir, ignore_errors=True)
            logger.debug("Cleaned up temp image directory.")

    def _migrate_as_cms(self, page_data: dict[str, Any], route: RouteResult) -> None:
        """Migrate a WP page as a PrestaShop CMS page."""
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

        # Determine CMS category
        cms_cat = route.cms_category_id or self.config.prestashop.cms_category_id

        if self.dry_run:
            logger.info(f"  🔍 [DRY RUN] Would create CMS page: {title}")
            logger.info(f"     Slug: {transformed['slug']}, CMS category: {cms_cat}")
            self.stats["cms_migrated"] += 1
            return

        # Check if page already exists (idempotency)
        existing_id = self.ps.find_cms_page_by_slug(transformed["slug"])

        if existing_id:
            logger.info(f"  🔄 CMS page exists (ID {existing_id}), updating...")
            success = self.ps.update_cms_page(
                page_id=existing_id,
                page_data=transformed,
                cms_category_id=cms_cat,
            )
        else:
            logger.info(f"  ✨ Creating new CMS page...")
            new_id = self.ps.create_cms_page(
                page_data=transformed,
                cms_category_id=cms_cat,
            )
            success = new_id is not None

        if success:
            self.stats["cms_migrated"] += 1
            logger.info(f"  ✅ CMS: {title}")
        else:
            self.stats["failed"] += 1
            logger.error(f"  ❌ CMS failed: {title}")

    def _migrate_as_product(self, page_data: dict[str, Any], route: RouteResult) -> None:
        """Update a PrestaShop product description from WP page content."""
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

        # Find matching PS product
        product_id = None
        if route.product_id:
            product_id = route.product_id
            logger.info(f"  🎯 Direct product ID mapping: {product_id}")
        elif route.product_reference:
            product_id = self.ps.find_product_by_reference(route.product_reference)
        elif route.match_by == "reference":
            product_id = self.ps.find_product_by_reference(slug)
        else:
            # match_by "name" — use title
            clean_title = html.unescape(title).strip()
            product_id = self.ps.find_product_by_name(clean_title)

        if not product_id:
            logger.warning(f"  ⚠️ No matching PS product for '{title}' — skipping")
            self.stats["skipped"] += 1
            return

        if self.dry_run:
            logger.info(f"  🔍 [DRY RUN] Would update product {product_id}: {title}")
            logger.info(f"     Content length: {len(transformed['content'])} chars")
            self.stats["product_updated"] += 1
            return

        success = self.ps.update_product_description(
            product_id=product_id,
            description=transformed["content"],
            meta_title=transformed.get("meta_title", ""),
            meta_description=transformed.get("meta_description", ""),
        )

        if success:
            self.stats["product_updated"] += 1
            logger.info(f"  ✅ Product {product_id}: {title}")
        else:
            self.stats["failed"] += 1
            logger.error(f"  ❌ Product update failed: {title}")

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

            self.stats["images"] += 1
