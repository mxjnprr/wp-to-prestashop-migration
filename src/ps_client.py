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
        self.session.verify = False  # Handle self-signed / invalid SSL certs
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

            # PrestaShop may return a list (empty results) or a dict
            if isinstance(data, list):
                return None
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

    @staticmethod
    def _sanitize_meta(text: str, max_len: int = 255) -> str:
        """Sanitize meta fields for PrestaShop's isCleanHtml validation."""
        import html
        import re
        if not text:
            return ""
        # Strip HTML tags (including CDATA, comments, etc.)
        text = re.sub(r'<[^>]*>', '', text)
        # Decode ALL HTML entities (&#8230; → …, &rsquo; → ', etc.)
        # Run twice to handle double-encoded entities
        text = html.unescape(html.unescape(text))
        # Replace smart/Unicode punctuation with ASCII equivalents
        replacements = {
            '\u2018': "'", '\u2019': "'",  # smart single quotes
            '\u201C': '"', '\u201D': '"',  # smart double quotes
            '\u2026': '...', '\u2013': '-', '\u2014': '-',  # ellipsis, dashes
            '\u00AB': '"', '\u00BB': '"',  # guillemets
            '\u2032': "'", '\u2033': '"',  # prime marks
            '\u00A0': ' ',  # non-breaking space
        }
        for orig, repl in replacements.items():
            text = text.replace(orig, repl)
        # Remove chars that PS isCleanHtml rejects: < > = { }
        text = re.sub(r'[<>={}]', '', text)
        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f]', '', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Truncate (use ASCII ellipsis to stay safe)
        if len(text) > max_len:
            text = text[:max_len - 3] + "..."
        return text

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

        # Multi-language fields — sanitize meta fields to avoid PS validation errors
        lang_fields = {
            "meta_title": self._sanitize_meta(page_data.get("meta_title", ""), 128),
            "meta_description": self._sanitize_meta(page_data.get("meta_description", ""), 512),
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
            try:
                root = ET.fromstring(resp.content)
                # Try multiple XPath patterns — PS structure varies by version
                for xpath in [
                    ".//content_management_system/id",
                    ".//content/id",
                    ".//cms/id",
                    ".//id",
                ]:
                    id_elem = root.find(xpath)
                    if id_elem is not None and id_elem.text:
                        new_id = int(id_elem.text)
                        logger.info(f"PS: created CMS page ID {new_id}")
                        return new_id

                # If HTTP was 200/201 but we couldn't find the ID, still count as success
                logger.warning(f"PS: page likely created (HTTP {resp.status_code}) but could not parse returned ID")
                logger.debug(f"PS: response body: {resp.text[:500]}")
                return -1  # Sentinel: created but unknown ID
            except ET.ParseError:
                logger.warning(f"PS: page likely created (HTTP {resp.status_code}) but response is not XML")
                logger.debug(f"PS: response body: {resp.text[:300]}")
                return -1

        except requests.exceptions.RequestException as e:
            logger.error(f"PS: failed to create CMS page: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.debug(f"PS: response body: {e.response.text[:500]}")
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

    # ─────────────────────────────────────────────────────────────
    # Product methods
    # ─────────────────────────────────────────────────────────────

    def find_product_by_name(self, name: str) -> Optional[int]:
        """
        Search for a product by name (case-insensitive partial match).
        Returns the first matching product ID, None if not found.
        """
        url = f"{self.api_base}/products"
        params = {
            "output_format": "JSON",
            "filter[name]": f"%{name}%",
            "display": "[id,name]",
            "limit": "5",
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            products = data.get("products", [])

            if isinstance(products, list) and len(products) > 0:
                pid = int(products[0].get("id", 0))
                pname = products[0].get("name", "")
                logger.info(f"PS: found product '{pname}' (ID {pid}) for query '{name}'")
                return pid or None
            elif isinstance(products, dict) and "id" in products:
                return int(products["id"]) or None

            logger.debug(f"PS: no product found for name '{name}'")
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.debug(f"PS: product name lookup for '{name}': {e}")
            return None

    def find_product_by_reference(self, reference: str) -> Optional[int]:
        """
        Search for a product by reference code.
        Returns the product ID, None if not found.
        """
        url = f"{self.api_base}/products"
        params = {
            "output_format": "JSON",
            "filter[reference]": reference,
            "display": "[id,reference,name]",
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            products = data.get("products", [])

            if isinstance(products, list) and len(products) > 0:
                pid = int(products[0].get("id", 0))
                logger.info(f"PS: found product (ID {pid}) for ref '{reference}'")
                return pid or None
            elif isinstance(products, dict) and "id" in products:
                return int(products["id"]) or None

            logger.debug(f"PS: no product found for reference '{reference}'")
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.debug(f"PS: product ref lookup for '{reference}': {e}")
            return None

    def get_product(self, product_id: int) -> Optional[dict]:
        """
        Fetch full product data (JSON).
        """
        url = f"{self.api_base}/products/{product_id}"
        params = {"output_format": "JSON"}
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("product", data)
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"PS: failed to get product {product_id}: {e}")
            return None

    def update_product_description(
        self,
        product_id: int,
        description: str,
        meta_title: str = "",
        meta_description: str = "",
    ) -> bool:
        """
        Update a product's description (and optionally SEO fields).
        Uses the PrestaShop XML API.
        """
        lang_id = str(self.default_lang_id)

        # First, fetch current product XML to preserve all other fields
        url = f"{self.api_base}/products/{product_id}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except (requests.exceptions.RequestException, ET.ParseError) as e:
            logger.error(f"PS: failed to fetch product {product_id} for update: {e}")
            return False

        product_elem = root.find(".//product")
        if product_elem is None:
            logger.error(f"PS: no <product> element in response for ID {product_id}")
            return False

        # Remove read-only nodes that PS rejects on PUT
        for readonly_tag in [
            "manufacturer_name", "quantity", "position_in_category",
            "type", "id_default_image", "associations",
        ]:
            elem = product_elem.find(readonly_tag)
            if elem is not None:
                product_elem.remove(elem)

        # Update description
        desc_elem = product_elem.find(f".//description/language[@id='{lang_id}']")
        if desc_elem is None:
            # Create the structure
            desc_parent = product_elem.find("description")
            if desc_parent is None:
                desc_parent = ET.SubElement(product_elem, "description")
            desc_elem = ET.SubElement(desc_parent, "language")
            desc_elem.set("id", lang_id)
        desc_elem.text = description

        # Update SEO fields if provided
        if meta_title:
            mt_elem = product_elem.find(f".//meta_title/language[@id='{lang_id}']")
            if mt_elem is None:
                mt_parent = product_elem.find("meta_title")
                if mt_parent is None:
                    mt_parent = ET.SubElement(product_elem, "meta_title")
                mt_elem = ET.SubElement(mt_parent, "language")
                mt_elem.set("id", lang_id)
            mt_elem.text = meta_title[:128]

        if meta_description:
            md_elem = product_elem.find(f".//meta_description/language[@id='{lang_id}']")
            if md_elem is None:
                md_parent = product_elem.find("meta_description")
                if md_parent is None:
                    md_parent = ET.SubElement(product_elem, "meta_description")
                md_elem = ET.SubElement(md_parent, "language")
                md_elem.set("id", lang_id)
            md_elem.text = meta_description[:512]

        # PUT back
        xml_payload = ET.tostring(root, encoding="unicode", xml_declaration=False)
        try:
            resp = self.session.put(
                url,
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"PS: updated product {product_id} description")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"PS: failed to update product {product_id}: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.debug(f"PS: response body: {e.response.text[:500]}")
            return False

    def list_products(self, limit: int = 100) -> list[dict]:
        """
        List all products (basic info) for preview/matching purposes.
        """
        url = f"{self.api_base}/products"
        params = {
            "output_format": "JSON",
            "display": "[id,name,reference,active]",
            "limit": str(limit),
        }
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            products = data.get("products", [])
            if isinstance(products, dict):
                products = [products]
            logger.info(f"PS: listed {len(products)} products")
            return products
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"PS: failed to list products: {e}")
            return []

    def list_cms_categories(self) -> list[dict]:
        """
        Auto-detect CMS categories from PrestaShop in a single API call.
        Fetches all CMS pages with display=full, extracts unique id_cms_category values.
        """
        url = f"{self.api_base}/content_management_system"
        try:
            resp = self.session.get(
                url,
                params={"display": "full", "output_format": "JSON", "limit": "100"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return []

            pages = data.get("content_management_system", data.get("content", []))
            if isinstance(pages, dict):
                pages = [pages]

            # Group pages by category — count only, page titles ≠ category names
            cat_counts: dict[int, int] = {}
            for p in pages:
                cat_id = int(p.get("id_cms_category", 1))
                cat_counts[cat_id] = cat_counts.get(cat_id, 0) + 1

            # Build result: category IDs with page counts
            # Actual names must come from config overrides (PS API doesn't expose them)
            result = []
            for cat_id in sorted(cat_counts.keys()):
                count = cat_counts[cat_id]
                result.append({
                    "id": cat_id,
                    "name": f"Catégorie {cat_id} ({count} pages)",
                })

            # Always include category 1 even if no pages
            if not any(c["id"] == 1 for c in result):
                result.insert(0, {"id": 1, "name": "Accueil"})

            logger.info(f"PS: auto-detected {len(result)} CMS categories")
            return result
        except Exception as e:
            logger.error(f"PS: failed to auto-detect CMS categories: {e}")
            return [{"id": 1, "name": "Accueil (défaut)"}]

