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
        # Merge mapping into config
        rules = []
        cms_slugs = sorted(s for s, t in self.assignments.items() if t == "cms")
        product_slugs = sorted(s for s, t in self.assignments.items() if t == "product")
        skip_slugs = sorted(s for s, t in self.assignments.items() if t == "skip")

        if product_slugs:
            rules.append({"name": "products", "target": "product", "match_by": "name", "slugs": product_slugs})
        if cms_slugs:
            rules.append({"name": "cms_pages", "target": "cms", "cms_category_id": 1, "slugs": cms_slugs})
        if skip_slugs:
            rules.append({"name": "skipped", "target": "skip", "slugs": skip_slugs})

        self.config["mapping"] = {"default": "skip", "rules": rules}

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


STATE = AppState()


# ── WordPress scanner ────────────────────────────────────────────

def scan_wordpress(wp_url: str) -> list[dict]:
    api_base = wp_url.rstrip("/") + "/wp-json/wp/v2"
    all_pages = []
    page_num = 1

    while True:
        url = f"{api_base}/pages"
        params = {
            "per_page": 100, "page": page_num, "status": "publish",
            "_fields": "id,title,content,excerpt,slug,date,modified,featured_media,yoast_head_json",
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        pages = resp.json()
        if not pages:
            break
        all_pages.extend(pages)
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        if page_num >= total_pages:
            break
        page_num += 1

    return all_pages


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

    return {
        "wp_id": page.get("id", 0),
        "title": title,
        "slug": slug,
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


def auto_categorize(page: dict) -> str:
    slug = page["slug"]
    title = page["title"]
    img_count = page["image_count"]
    size = page["content_size_bytes"]

    if img_count >= 10 and size > 15000:
        return "product"
    if slug in ("sellettes", "accessoires", "saks", "produits", "kockpits",
                "kontainers", "produits-stoppes", "vetements", "parachutes"):
        return "skip"
    if re.match(r'^[a-z]+-[a-z]+(-\d+)?$', slug):
        words = title.split()
        if len(words) >= 2 and all(w[0:1].isupper() for w in words if w):
            return "cms"
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
                STATE.wp_pages = scan_wordpress(wp_url)
                STATE.analyzed = [analyze_page(p) for p in STATE.wp_pages]
                STATE.analyzed.sort(key=lambda p: p["slug"])

                # Auto-categorize
                STATE.assignments = {}
                for p in STATE.analyzed:
                    STATE.assignments[p["slug"]] = auto_categorize(p)

                self._send_json({
                    "total": len(STATE.analyzed),
                    "cms": sum(1 for t in STATE.assignments.values() if t == "cms"),
                    "product": sum(1 for t in STATE.assignments.values() if t == "product"),
                    "skip": sum(1 for t in STATE.assignments.values() if t == "skip"),
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/pages/route":
            slug = body.get("slug", "")
            target = body.get("target", "skip")
            if slug and target in ("cms", "product", "skip"):
                STATE.assignments[slug] = target
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Invalid slug or target"}, 400)

        elif path == "/api/pages/bulk-route":
            slugs = body.get("slugs", [])
            target = body.get("target", "skip")
            if target in ("cms", "product", "skip"):
                for slug in slugs:
                    STATE.assignments[slug] = target
                self._send_json({"ok": True, "count": len(slugs)})
            else:
                self._send_json({"error": "Invalid target"}, 400)

        elif path == "/api/pages/auto-categorize":
            for p in STATE.analyzed:
                STATE.assignments[p["slug"]] = auto_categorize(p)
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
