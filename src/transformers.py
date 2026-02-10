"""
HTML content transformers.
Parses WordPress HTML, extracts images, rewrites image URLs for PrestaShop.
"""

import logging
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .utils import decode_html_entities, strip_html_tags, sanitize_slug, truncate

logger = logging.getLogger("wp2presta")


class ContentTransformer:
    """Transforms WordPress page content for PrestaShop compatibility."""

    def __init__(self, wp_base_url: str, ps_base_url: str, image_temp_dir: str = "temp_images"):
        self.wp_base_url = wp_base_url.rstrip("/")
        self.ps_base_url = ps_base_url.rstrip("/")
        self.image_temp_dir = image_temp_dir
        self.discovered_images: list[dict[str, str]] = []

    def transform_page(self, page_data: dict[str, Any]) -> dict[str, Any]:
        """
        Apply all transformations to a WordPress page.
        Returns transformed data ready for PrestaShop injection.
        """
        transformed = dict(page_data)

        # 1. Decode HTML entities in title and meta
        transformed["title"] = decode_html_entities(transformed.get("title", ""))
        transformed["meta_title"] = decode_html_entities(transformed.get("meta_title", ""))
        transformed["meta_title"] = truncate(transformed["meta_title"], 255)

        # 2. Clean meta description (strip tags, decode, truncate)
        meta_desc = transformed.get("meta_description", "")
        meta_desc = strip_html_tags(meta_desc)
        meta_desc = decode_html_entities(meta_desc)
        meta_desc = truncate(meta_desc, 512)
        transformed["meta_description"] = meta_desc

        # 3. Sanitize slug
        transformed["slug"] = sanitize_slug(transformed.get("slug", ""))

        # 4. Transform HTML content (images, WP-specific markup)
        content = transformed.get("content", "")
        content = self._transform_html_content(content)
        transformed["content"] = content

        return transformed

    def _transform_html_content(self, html_content: str) -> str:
        """
        Process HTML content:
        - Strip WordPress shortcodes (Divi, WPBakery, etc.)
        - Discover and catalog images for download
        - Remove WordPress-specific CSS classes (wp-block-*, etc.)
        - Clean up empty/unnecessary elements
        """
        if not html_content:
            return ""

        # 1. Extract image URLs from shortcode attributes before stripping
        #    e.g. [et_pb_fullwidth_image src="https://...jpg" ...]
        html_content = self._extract_shortcode_images(html_content)

        # 2. Strip ALL WordPress shortcodes (Divi, WPBakery, etc.)
        html_content = self._strip_shortcodes(html_content)

        soup = BeautifulSoup(html_content, "html.parser")

        # Process images (standard <img> tags)
        self._process_images(soup)

        # Remove WordPress-specific classes
        self._clean_wp_classes(soup)

        # Remove empty paragraphs
        for p in soup.find_all("p"):
            if not p.get_text(strip=True) and not p.find("img"):
                p.decompose()

        return str(soup)

    def _extract_shortcode_images(self, content: str) -> str:
        """Extract image URLs from shortcode attributes and convert to <img> tags."""
        # Match shortcodes with src= attribute (Divi images, galleries, etc.)
        # [et_pb_fullwidth_image src="https://...jpg" ...] → <img src="..."/>
        img_pattern = re.compile(
            r'\[et_pb_(?:fullwidth_)?image\s+[^\]]*?src=["\u00BB]([^"\u00AB\]]+)["\u00AB][^\]]*\]',
            re.IGNORECASE
        )
        content = img_pattern.sub(r'<img src="\1" />', content)
        return content

    @staticmethod
    def _strip_shortcodes(content: str) -> str:
        """Remove all WordPress shortcodes [tag ...] and [/tag], keeping inner text."""
        # Remove closing shortcode tags: [/et_pb_text], [/vc_column], etc.
        content = re.sub(r'\[/[^\]]+\]', '', content)
        # Remove self-closing and opening shortcode tags: [et_pb_section ...], [vc_row], etc.
        # Use » and « as quote variants (Divi encodes quotes this way)
        content = re.sub(r'\[[a-zA-Z_][^\]]*\]', '', content)
        # Clean up excessive blank lines left behind
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()

    def _process_images(self, soup: BeautifulSoup) -> None:
        """
        Find all images in the content, record them for download,
        and rewrite their src URLs.
        """
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue

            # Resolve relative URLs
            if src.startswith("/"):
                src = urljoin(self.wp_base_url, src)

            # Only process images from the WordPress domain
            parsed = urlparse(src)
            wp_parsed = urlparse(self.wp_base_url)
            if parsed.hostname and parsed.hostname != wp_parsed.hostname:
                logger.debug(f"Skipping external image: {src}")
                continue

            # Extract filename
            filename = os.path.basename(parsed.path)
            if not filename:
                continue

            # Record image for download
            new_url = f"{self.ps_base_url}/img/cms/{filename}"
            self.discovered_images.append({
                "original_url": src,
                "filename": filename,
                "new_url": new_url,
            })

            # Rewrite the src attribute
            img["src"] = new_url
            logger.debug(f"Image rewrite: {src} → {new_url}")

            # Also rewrite srcset if present
            if img.get("srcset"):
                # Remove srcset as WP-specific responsive images won't work in Presta
                del img["srcset"]

            # Remove WP-specific size classes
            if img.get("class"):
                img["class"] = [
                    c for c in img["class"]
                    if not c.startswith("wp-image-") and not c.startswith("size-")
                ]

    def _clean_wp_classes(self, soup: BeautifulSoup) -> None:
        """Remove WordPress-specific CSS classes from all elements."""
        wp_class_patterns = [
            re.compile(r"^wp-block-"),
            re.compile(r"^wp-image-"),
            re.compile(r"^has-"),
            re.compile(r"^is-layout-"),
            re.compile(r"^alignwide$"),
            re.compile(r"^alignfull$"),
        ]

        for element in soup.find_all(True):  # All tags
            classes = element.get("class", [])
            if not classes:
                continue

            cleaned = [
                c for c in classes
                if not any(pattern.match(c) for pattern in wp_class_patterns)
            ]

            if cleaned:
                element["class"] = cleaned
            elif "class" in element.attrs:
                del element["class"]

    def get_discovered_images(self) -> list[dict[str, str]]:
        """Return the list of images discovered during transformation."""
        return self.discovered_images

    def reset_images(self) -> None:
        """Reset the discovered images list (between pages)."""
        self.discovered_images = []
