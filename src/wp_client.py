"""
WordPress REST API client.
Fetches published pages, media metadata, and downloads images.
"""

import logging
from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("wp2presta")


class WordPressClient:
    """Client for the WordPress REST API (WP 4.7+)."""

    def __init__(self, api_base: str, username: str = "", app_password: str = ""):
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "WP2Presta-Migration/1.0",
            "Accept": "application/json",
        })
        if username and app_password:
            self.session.auth = HTTPBasicAuth(username, app_password)
            logger.info("WordPress: using authenticated access")
        else:
            logger.info("WordPress: using anonymous access (public content only)")

    def get_pages(self, per_page: int = 100) -> list[dict[str, Any]]:
        """
        Fetch all published pages, handling WP REST API pagination.
        Returns a list of page objects.
        """
        all_pages = []
        page_num = 1

        while True:
            url = f"{self.api_base}/pages"
            params = {
                "per_page": per_page,
                "page": page_num,
                "status": "publish",
                "_fields": "id,title,content,excerpt,slug,date,modified,featured_media,meta,yoast_head_json",
            }
            logger.debug(f"WP API: GET {url} (page {page_num})")

            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"WP API error fetching pages (page {page_num}): {e}")
                break

            pages = resp.json()
            if not pages:
                break

            all_pages.extend(pages)
            logger.info(f"WP: fetched {len(pages)} pages (batch {page_num})")

            # Check if there are more pages
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            if page_num >= total_pages:
                break
            page_num += 1

        logger.info(f"WP: total pages fetched: {len(all_pages)}")
        return all_pages

    def get_media(self, media_id: int) -> Optional[dict[str, Any]]:
        """Fetch metadata for a single media item."""
        if not media_id:
            return None

        url = f"{self.api_base}/media/{media_id}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"WP: failed to fetch media {media_id}: {e}")
            return None

    def download_image(self, image_url: str) -> Optional[bytes]:
        """Download an image by URL and return the binary content."""
        try:
            logger.debug(f"WP: downloading image: {image_url}")
            resp = self.session.get(image_url, timeout=60)
            resp.raise_for_status()
            return resp.content
        except requests.exceptions.RequestException as e:
            logger.warning(f"WP: failed to download image {image_url}: {e}")
            return None

    def extract_page_data(self, wp_page: dict[str, Any]) -> dict[str, Any]:
        """
        Extract and normalize relevant fields from a WP page API response.
        Returns a flat dict ready for transformation.
        """
        # Basic fields
        title = wp_page.get("title", {}).get("rendered", "")
        content = wp_page.get("content", {}).get("rendered", "")
        excerpt = wp_page.get("excerpt", {}).get("rendered", "")
        slug = wp_page.get("slug", "")

        # Try to get Yoast SEO data if available
        yoast = wp_page.get("yoast_head_json", {}) or {}
        meta_title = yoast.get("title", "") or title
        meta_description = yoast.get("description", "") or excerpt

        return {
            "wp_id": wp_page.get("id"),
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "slug": slug,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "featured_media_id": wp_page.get("featured_media", 0),
            "date": wp_page.get("date", ""),
            "modified": wp_page.get("modified", ""),
        }
