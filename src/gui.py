#!/usr/bin/env python3
"""
Web GUI backend for the WP → PrestaShop migration tool.
Serves the SPA frontend and provides JSON API endpoints.

Launch: python -m src.gui [--port 8585]
"""

import html
import json
import logging
import os
import re
import sys
import threading
import webbrowser
from functools import partial
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests
import yaml

logger = logging.getLogger("wp2presta.gui")

# ── Shared state ─────────────────────────────────────────────────

class AppState:
    """Holds all shared state for the GUI session."""

    def __init__(self):
        self.config: dict = {}
        self.wp_pages: list[dict] = []
        self.analyzed: list[dict] = []
        self.assignments: dict[str, str] = {}     # slug → target
        self.page_options: dict[str, dict] = {}   # slug → {cms_category_id, product_id, product_reference, match_by}
        self.migration_log: list[str] = []
        self.migration_running: bool = False
        self.migration_progress: dict = {"current": 0, "total": 0, "status": "idle"}
        self.config_path: str = "config.yaml"

    def load_config(self, path: str = None):
        p = path or self.config_path
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
            self.config_path = p
        else:
            self.config = {
                "wordpress": {"url": ""},
                "prestashop": {"url": "", "api_key": "", "default_lang_id": 1, "cms_category_id": 1},
                "migration": {"dry_run": True, "download_images": True, "log_file": "migration.log"},
            }

    def save_config(self):
        # Group by target and options to create fine-grained rules
        from collections import defaultdict
        rules = []

        # Group CMS pages by category ID
        cms_by_cat: dict[int, list[str]] = defaultdict(list)
        for slug, target in self.assignments.items():
            if target == "cms":
                opts = self.page_options.get(slug, {})
                cat_id = opts.get("cms_category_id") or self.config.get("prestashop", {}).get("cms_category_id", 1)
                cms_by_cat[cat_id].append(slug)

        for cat_id, slugs in sorted(cms_by_cat.items()):
            rules.append({
                "name": f"cms_cat_{cat_id}",
                "target": "cms",
                "cms_category_id": cat_id,
                "slugs": sorted(slugs),
            })

        # Group Product pages: direct ID mappings vs match-by-name/reference
        product_map = []
        product_by_ref = []
        product_by_name = []
        for slug, target in self.assignments.items():
            if target != "product":
                continue
            opts = self.page_options.get(slug, {})
            if opts.get("product_id"):
                product_map.append({"slug": slug, "product_id": opts["product_id"]})
            elif opts.get("product_reference"):
                product_by_ref.append({"slug": slug, "product_reference": opts["product_reference"]})
            else:
                match = opts.get("match_by", "name")
                if match == "reference":
                    product_by_ref.append({"slug": slug})
                else:
                    product_by_name.append(slug)

        if product_map:
            rules.append({
                "name": "products_by_id",
                "target": "product",
                "product_map": [{"slug": p["slug"], "product_id": p["product_id"]} for p in sorted(product_map, key=lambda x: x["slug"])],
            })
        if product_by_ref:
            rules.append({
                "name": "products_by_reference",
                "target": "product",
                "match_by": "reference",
                "slugs": sorted(p["slug"] for p in product_by_ref),
            })
        if product_by_name:
            rules.append({
                "name": "products_by_name",
                "target": "product",
                "match_by": "name",
                "slugs": sorted(product_by_name),
            })

        # Skip rules
        skip_slugs = sorted(s for s, t in self.assignments.items() if t == "skip")
        if skip_slugs:
            rules.append({"name": "skipped", "target": "skip", "slugs": skip_slugs})

        self.config["mapping"] = {"default": "skip", "rules": rules}

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


STATE = AppState()


# ── WordPress scanner ────────────────────────────────────────────

# Spam category keywords to auto-filter
SPAM_KEYWORDS = [
    "casino", "1win", "1xbet", "aviator", "plinko", "bet", "poker",
    "gambling", "slot", "roulette", "blackjack", "mostbet", "pinco",
    "masalbet", "basaribet", "bankobet", "glory-casinos", "pelican-casino",
    "king-johnnie", "vovan", "ozwin", "maribet", "b1bet", "bbrbet",
    "888starz", "22bet", "casibom", "book-of-ra",
]


def _fetch_wp_categories(api_base: str) -> dict[int, str]:
    """Fetch all WP categories and return {id: name} mapping."""
    cats = {}
    page_num = 1
    while True:
        try:
            resp = requests.get(
                f"{api_base}/categories",
                params={"per_page": 100, "page": page_num, "_fields": "id,name,slug,count"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for c in data:
                cats[c["id"]] = c.get("name", c.get("slug", ""))
            if page_num >= int(resp.headers.get("X-WP-TotalPages", 1)):
                break
            page_num += 1
        except Exception:
            break
    return cats


def _is_spam(slug: str, title: str) -> bool:
    """Check if a post looks like spam based on slug/title."""
    text = (slug + " " + title).lower()
    return any(kw in text for kw in SPAM_KEYWORDS)


def _fetch_all_items(api_base: str, endpoint: str, wp_type: str) -> list[dict]:
    """Generic paginated WP REST API fetcher."""
    all_items = []
    page_num = 1
    fields = "id,title,content,excerpt,slug,date,modified,featured_media,yoast_head_json"
    if endpoint == "posts":
        fields += ",categories"

    while True:
        params = {
            "per_page": 100, "page": page_num, "status": "publish",
            "_fields": fields,
        }
        resp = requests.get(f"{api_base}/{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break
        for item in items:
            item["_wp_type"] = wp_type
        all_items.extend(items)
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        if page_num >= total_pages:
            break
        page_num += 1

    return all_items


def scan_wordpress(wp_url: str) -> tuple[list[dict], dict[int, str]]:
    """Fetch all published pages AND posts. Returns (items, categories)."""
    api_base = wp_url.rstrip("/") + "/wp-json/wp/v2"

    # Fetch categories first
    categories = _fetch_wp_categories(api_base)

    # Fetch pages + posts
    pages = _fetch_all_items(api_base, "pages", "page")
    posts = _fetch_all_items(api_base, "posts", "post")

    # Filter out spam posts
    clean_posts = []
    spam_count = 0
    for p in posts:
        title = p.get("title", {}).get("rendered", "")
        slug = p.get("slug", "")
        if _is_spam(slug, title):
            spam_count += 1
        else:
            clean_posts.append(p)

    if spam_count:
        logger.info(f"Filtered {spam_count} spam posts")

    return pages + clean_posts, categories


def analyze_page(page: dict) -> dict:
    title = html.unescape(page.get("title", {}).get("rendered", "(sans titre)"))
    content_html = page.get("content", {}).get("rendered", "")
    slug = page.get("slug", "")
    yoast = page.get("yoast_head_json", {}) or {}
    images = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content_html, re.I)
    size = len(content_html.encode("utf-8"))

    # Text preview
    text = re.sub(r'<[^>]+>', ' ', content_html)
    text = re.sub(r'\s+', ' ', text).strip()
    text = html.unescape(text)[:300]

    # Warnings
    warnings = []
    if re.search(r'wpcf7|contact-form', content_html, re.I):
        warnings.append("Formulaire CF7")
    if re.search(r'\[/?[a-z_]+', content_html):
        warnings.append("Shortcodes")
    if re.search(r'et_pb_', content_html, re.I):
        warnings.append("Divi builder")

    # Size human
    if size < 1024:
        size_h = f"{size} B"
    elif size < 1024 * 1024:
        size_h = f"{size / 1024:.1f} KB"
    else:
        size_h = f"{size / (1024 * 1024):.1f} MB"

    # Resolve category names
    cat_ids = page.get("categories", [])
    wp_type = page.get("_wp_type", "page")

    return {
        "wp_id": page.get("id", 0),
        "title": title,
        "slug": slug,
        "wp_type": wp_type,
        "wp_categories": cat_ids,
        "content_size": size_h,
        "content_size_bytes": size,
        "content_preview": text,
        "image_count": len(images),
        "image_urls": images[:3],
        "meta_title": html.unescape(yoast.get("title", "")) if yoast.get("title") else "",
        "meta_description": html.unescape(yoast.get("description", ""))[:300] if yoast.get("description") else "",
        "has_seo": bool(yoast.get("title") or yoast.get("description")),
        "warnings": warnings,
        "date": page.get("date", "")[:10],
        "modified": page.get("modified", "")[:10],
    }


def auto_categorize(page: dict, categories: dict[int, str] = None) -> str:
    slug = page["slug"]
    title = page["title"]
    img_count = page["image_count"]
    size = page["content_size_bytes"]
    wp_type = page.get("wp_type", "page")
    cat_ids = page.get("wp_categories", [])

    # Resolve category names
    cat_names = []
    if categories and cat_ids:
        cat_names = [categories.get(c, "").lower() for c in cat_ids]

    # Posts (articles) → default to CMS unless spam
    if wp_type == "post":
        # Check if spam by category name
        for cn in cat_names:
            if any(kw in cn for kw in SPAM_KEYWORDS):
                return "skip"
        return "cms"  # All legit posts → CMS by default

    # Pages: product-like (many images + large content)
    if img_count >= 10 and size > 15000:
        return "product"

    # Pages: index/listing pages
    if slug in ("sellettes", "accessoires", "saks", "produits", "kockpits",
                "kontainers", "produits-stoppes", "vetements", "parachutes"):
        return "skip"

    # Pages: ambassador profiles (First Last pattern)
    if re.match(r'^[a-z]+-[a-z]+(-\d+)?$', slug):
        words = title.split()
        if len(words) >= 2 and all(w[0:1].isupper() for w in words if w):
            return "cms"

    # Pages: known content pages
    content_slugs = ["valeurs", "garantie", "recrutement", "contact", "evenements",
                     "news", "recits", "team", "confidentialite", "documents-securite"]
    if slug in content_slugs:
        return "cms"

    return "skip"


# ── Migration runner ─────────────────────────────────────────────

def run_migration_thread(dry_run: bool):
    STATE.migration_running = True
    STATE.migration_log = []
    STATE.migration_progress = {"current": 0, "total": len(STATE.analyzed), "status": "running"}

    try:
        from .config import load_config
        from .migrator import Migrator
        from .utils import setup_logging

        STATE.save_config()
        config = load_config(STATE.config_path)
        config.migration.dry_run = dry_run

        setup_logging(log_file=config.migration.log_file, verbose=True)

        # Patch logger to capture output
        class GUIHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)
                STATE.migration_log.append(msg)
                # Update progress from log messages
                match = re.search(r'\[(\d+)/(\d+)\]', msg)
                if match:
                    STATE.migration_progress["current"] = int(match.group(1))
                    STATE.migration_progress["total"] = int(match.group(2))

        gui_handler = GUIHandler()
        gui_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger("wp2presta").addHandler(gui_handler)

        migrator = Migrator(config)
        migrator.run()

        STATE.migration_progress["status"] = "done"
        STATE.migration_progress["stats"] = migrator.stats
    except Exception as e:
        STATE.migration_log.append(f"❌ Erreur fatale: {e}")
        STATE.migration_progress["status"] = "error"
        STATE.migration_progress["error"] = str(e)
    finally:
        STATE.migration_running = False


# ── HTTP Handler ─────────────────────────────────────────────────

class GUIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silence HTTP logs

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/config":
            self._send_json(STATE.config)
        elif path == "/api/pages":
            pages = []
            for p in STATE.analyzed:
                p_copy = dict(p)
                p_copy["target"] = STATE.assignments.get(p["slug"], "skip")
                p_copy["options"] = STATE.page_options.get(p["slug"], {})
                pages.append(p_copy)
            self._send_json(pages)
        elif path == "/api/migrate/status":
            self._send_json({
                "progress": STATE.migration_progress,
                "log": STATE.migration_log[-50:],
                "running": STATE.migration_running,
            })
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/config":
            STATE.config.update(body)
            STATE.save_config()
            self._send_json({"ok": True})

        elif path == "/api/test-connection":
            result = {"wordpress": False, "prestashop": False, "wp_error": "", "ps_error": ""}
            wp_url = body.get("wp_url") or STATE.config.get("wordpress", {}).get("url", "")
            ps_url = body.get("ps_url") or STATE.config.get("prestashop", {}).get("url", "")
            ps_key = body.get("ps_key") or STATE.config.get("prestashop", {}).get("api_key", "")

            if wp_url:
                try:
                    r = requests.get(wp_url.rstrip("/") + "/wp-json/wp/v2/pages?per_page=1", timeout=10)
                    r.raise_for_status()
                    result["wordpress"] = True
                except Exception as e:
                    result["wp_error"] = str(e)

            if ps_url and ps_key:
                try:
                    r = requests.get(
                        ps_url.rstrip("/") + "/api/",
                        auth=(ps_key, ""), timeout=10,
                    )
                    result["prestashop"] = r.status_code == 200
                    if not result["prestashop"]:
                        result["ps_error"] = f"HTTP {r.status_code}"
                except Exception as e:
                    result["ps_error"] = str(e)

            self._send_json(result)

        elif path == "/api/scan":
            wp_url = body.get("url") or STATE.config.get("wordpress", {}).get("url", "")
            if not wp_url:
                self._send_json({"error": "URL WordPress requise"}, 400)
                return

            try:
                STATE.wp_pages, wp_categories = scan_wordpress(wp_url)
                STATE.analyzed = [analyze_page(p) for p in STATE.wp_pages]
                STATE.analyzed.sort(key=lambda p: p["slug"])

                # Resolve category names and store for later use
                STATE._wp_categories = wp_categories
                for item in STATE.analyzed:
                    item["category_names"] = [
                        wp_categories.get(c, "?") for c in item.get("wp_categories", [])
                    ]

                # Auto-categorize
                STATE.assignments = {}
                for p in STATE.analyzed:
                    STATE.assignments[p["slug"]] = auto_categorize(p, wp_categories)

                page_count = sum(1 for p in STATE.analyzed if p.get("wp_type") == "page")
                post_count = sum(1 for p in STATE.analyzed if p.get("wp_type") == "post")

                self._send_json({
                    "total": len(STATE.analyzed),
                    "pages": page_count,
                    "posts": post_count,
                    "cms": sum(1 for t in STATE.assignments.values() if t == "cms"),
                    "product": sum(1 for t in STATE.assignments.values() if t == "product"),
                    "skip": sum(1 for t in STATE.assignments.values() if t == "skip"),
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/pages/route":
            slug = body.get("slug", "")
            target = body.get("target", "skip")
            options = body.get("options", {})
            if slug and target in ("cms", "product", "skip"):
                STATE.assignments[slug] = target
                if options:
                    STATE.page_options[slug] = {**STATE.page_options.get(slug, {}), **options}
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Invalid slug or target"}, 400)

        elif path == "/api/pages/bulk-route":
            slugs = body.get("slugs", [])
            target = body.get("target", "skip")
            options = body.get("options", {})
            if target in ("cms", "product", "skip"):
                for slug in slugs:
                    STATE.assignments[slug] = target
                    if options:
                        STATE.page_options[slug] = {**STATE.page_options.get(slug, {}), **options}
                self._send_json({"ok": True, "count": len(slugs)})
            else:
                self._send_json({"error": "Invalid target"}, 400)

        elif path == "/api/pages/options":
            slug = body.get("slug", "")
            options = body.get("options", {})
            if slug:
                STATE.page_options[slug] = {**STATE.page_options.get(slug, {}), **options}
                self._send_json({"ok": True, "options": STATE.page_options[slug]})
            else:
                self._send_json({"error": "Slug requis"}, 400)

        elif path == "/api/pages/auto-categorize":
            cats = getattr(STATE, '_wp_categories', {})
            for p in STATE.analyzed:
                STATE.assignments[p["slug"]] = auto_categorize(p, cats)
            self._send_json({
                "cms": sum(1 for t in STATE.assignments.values() if t == "cms"),
                "product": sum(1 for t in STATE.assignments.values() if t == "product"),
                "skip": sum(1 for t in STATE.assignments.values() if t == "skip"),
            })

        elif path == "/api/migrate":
            if STATE.migration_running:
                self._send_json({"error": "Migration already running"}, 409)
                return
            dry_run = body.get("dry_run", True)
            STATE.save_config()
            thread = threading.Thread(target=run_migration_thread, args=(dry_run,), daemon=True)
            thread.start()
            self._send_json({"ok": True, "dry_run": dry_run})

        elif path == "/api/save-mapping":
            STATE.save_config()
            self._send_json({"ok": True, "path": STATE.config_path})

        else:
            self.send_error(404)

    def _serve_html(self):
        from .gui_assets import get_html
        body = get_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── Main ─────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="WP→PS Migration GUI")
    parser.add_argument("--port", "-p", type=int, default=8585)
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    STATE.config_path = args.config
    STATE.load_config(args.config)

    server = HTTPServer(("0.0.0.0", args.port), GUIHandler)
    url = f"http://localhost:{args.port}"

    print(f"\n  ╔══════════════════════════════════════════════╗")
    print(f"  ║  WP → PrestaShop Migration GUI              ║")
    print(f"  ║  {url:<43} ║")
    print(f"  ╚══════════════════════════════════════════════╝\n")

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêt du serveur.")
        server.shutdown()


if __name__ == "__main__":
    main()
