"""
PrestaShop Webservice API client.
Manages CMS pages via XML payloads.
"""

import logging
from typing import Any, Optional
from xml.etree import ElementTree as ET

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("wp2presta")


class PrestaShopClient:
    """Client for the PrestaShop Webservice API (XML-based)."""

    def __init__(self, api_base: str, api_key: str, default_lang_id: int = 1):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.default_lang_id = default_lang_id
        self.session = requests.Session()
        # PrestaShop Webservice uses API key as username, no password
        self.session.auth = HTTPBasicAuth(api_key, "")
        self.session.headers.update({
            "User-Agent": "WP2Presta-Migration/1.0",
        })

    def test_connection(self) -> bool:
        """Test the API connection and key validity."""
        try:
            resp = self.session.get(f"{self.api_base}/", timeout=10)
            if resp.status_code == 200:
                logger.info("PrestaShop: API connection OK ✅")
                return True
            elif resp.status_code == 401:
                logger.error("PrestaShop: Invalid API key (401 Unauthorized)")
                return False
            else:
                logger.error(f"PrestaShop: API returned status {resp.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"PrestaShop: connection failed: {e}")
            return False

    def find_cms_page_by_slug(self, slug: str) -> Optional[int]:
        """
        Search for an existing CMS page by its link_rewrite (slug).
        Returns the PrestaShop CMS page ID if found, None otherwise.
        """
        url = f"{self.api_base}/content_management_system"
        params = {
            "output_format": "JSON",
            "filter[link_rewrite]": slug,
            "display": "[id]",
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            cms_pages = data.get("content_management_system", [])

            # PrestaShop returns different structures depending on result count
            if isinstance(cms_pages, list) and len(cms_pages) > 0:
                return int(cms_pages[0].get("id", 0)) or None
            elif isinstance(cms_pages, dict) and "id" in cms_pages:
                return int(cms_pages["id"]) or None

            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.debug(f"PS: slug lookup for '{slug}': {e}")
            return None

    def get_blank_cms_schema(self) -> Optional[ET.Element]:
        """
        Fetch the blank XML schema for a CMS page from the API.
        This gives us the correct structure to fill in.
        """
        url = f"{self.api_base}/content_management_system"
        params = {"schema": "blank"}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            return root
        except (requests.exceptions.RequestException, ET.ParseError) as e:
            logger.error(f"PS: failed to get CMS schema: {e}")
            return None

    def _build_cms_xml(
        self,
        page_data: dict[str, Any],
        cms_category_id: int,
        existing_id: Optional[int] = None,
    ) -> str:
        """
        Build the XML payload for creating or updating a CMS page.
        """
        lang_id = str(self.default_lang_id)

        # Build XML manually for controlled output
        prestashop = ET.Element("prestashop")
        prestashop.set("xmlns:xlink", "http://www.w3.org/1999/xlink")
        cms = ET.SubElement(prestashop, "content_management_system")

        if existing_id:
            id_elem = ET.SubElement(cms, "id")
            id_elem.text = str(existing_id)

        # CMS category  
        cat_elem = ET.SubElement(cms, "id_cms_category")
        cat_elem.text = str(cms_category_id)

        # Active
        active_elem = ET.SubElement(cms, "active")
        active_elem.text = "1"

        # Indexation (allow search indexing)
        index_elem = ET.SubElement(cms, "indexation")
        index_elem.text = "1"

        # Multi-language fields
        lang_fields = {
            "meta_title": page_data.get("meta_title", ""),
            "meta_description": page_data.get("meta_description", ""),
            "meta_keywords": "",
            "content": page_data.get("content", ""),
            "link_rewrite": page_data.get("slug", ""),
        }

        for field_name, value in lang_fields.items():
            field_elem = ET.SubElement(cms, field_name)
            lang_elem = ET.SubElement(field_elem, "language")
            lang_elem.set("id", lang_id)
            # Use CDATA-like approach — we'll handle special chars
            lang_elem.text = value

        return ET.tostring(prestashop, encoding="unicode", xml_declaration=False)

    def create_cms_page(
        self,
        page_data: dict[str, Any],
        cms_category_id: int,
    ) -> Optional[int]:
        """
        Create a new CMS page in PrestaShop.
        Returns the new page ID on success, None on failure.
        """
        xml_payload = self._build_cms_xml(page_data, cms_category_id)
        url = f"{self.api_base}/content_management_system"

        try:
            resp = self.session.post(
                url,
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=30,
            )
            resp.raise_for_status()

            # Parse response to get new ID
            root = ET.fromstring(resp.content)
            id_elem = root.find(".//content_management_system/id")
            if id_elem is not None and id_elem.text:
                new_id = int(id_elem.text)
                logger.info(f"PS: created CMS page ID {new_id}")
                return new_id
            else:
                logger.warning("PS: page created but could not parse returned ID")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"PS: failed to create CMS page: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.debug(f"PS: response body: {e.response.text[:500]}")
            return None
        except ET.ParseError as e:
            logger.error(f"PS: failed to parse create response: {e}")
            return None

    def update_cms_page(
        self,
        page_id: int,
        page_data: dict[str, Any],
        cms_category_id: int,
    ) -> bool:
        """
        Update an existing CMS page in PrestaShop.
        Returns True on success.
        """
        xml_payload = self._build_cms_xml(page_data, cms_category_id, existing_id=page_id)
        url = f"{self.api_base}/content_management_system/{page_id}"

        try:
            resp = self.session.put(
                url,
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"PS: updated CMS page ID {page_id}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"PS: failed to update CMS page {page_id}: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.debug(f"PS: response body: {e.response.text[:500]}")
            return False
