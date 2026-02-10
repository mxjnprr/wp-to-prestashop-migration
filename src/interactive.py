#!/usr/bin/env python3
"""
Interactive CLI wizard for WordPress → PrestaShop migration.
Scans WordPress, lists all content, and lets the user choose
destinations interactively before executing the migration.
"""

import html
import json
import os
import re
import sys
from typing import Any, Optional

import requests
import yaml


# ── ANSI colors ──────────────────────────────────────────────────

class C:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDER = "\033[4m"

    # Foreground
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    # Backgrounds (for badges)
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_GRAY = "\033[100m"
    BG_GREEN = "\033[42m"

    @staticmethod
    def badge(text: str, bg: str, fg: str = "\033[37m") -> str:
        return f"{bg}{fg} {text} {C.RESET}"


# ── Helpers ──────────────────────────────────────────────────────

def _clean_title(raw: dict) -> str:
    return html.unescape(raw.get("title", {}).get("rendered", "(sans titre)"))


def _content_size(raw: dict) -> str:
    content = raw.get("content", {}).get("rendered", "")
    size = len(content.encode("utf-8"))
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _image_count(raw: dict) -> int:
    content = raw.get("content", {}).get("rendered", "")
    return len(re.findall(r'<img[^>]+src=', content, re.I))


def _auto_category(slug: str, title: str, page: dict) -> str:
    """Heuristic auto-categorization."""
    content_html = page.get("content", {}).get("rendered", "")
    img_count = _image_count(page)
    size = len(content_html.encode("utf-8"))

    # Known product patterns
    product_keywords = [
        "sellette", "harness", "sak", "parachute", "connecteur",
        "accelerateur", "kontainer", "kockpit",
    ]

    # Check if it looks like a product page (rich content with many images)
    if img_count >= 10 and size > 15000:
        return "product"

    # Check slugs that look like ambassador profiles (First-Last pattern)
    if re.match(r'^[a-z]+-[a-z]+(-\d+)?$', slug) and title.replace(" ", "").isalpha():
        words = title.split()
        if len(words) >= 2 and words[0][0].isupper() and words[-1][0].isupper():
            return "ambassador"

    # Category overview pages
    category_slugs = ["sellettes", "accessoires", "saks", "produits", "kockpits",
                      "kontainers", "produits-stoppes"]
    if slug in category_slugs or slug.endswith("-2"):
        return "category"

    # Content pages
    content_slugs = ["valeurs", "garantie", "recrutement", "contact", "evenements",
                     "news", "recits", "team", "confidentialite", "documents-securite"]
    if slug in content_slugs:
        return "content"

    return "other"


# ── WordPress fetcher ────────────────────────────────────────────

def fetch_all_pages(wp_url: str) -> list[dict]:
    """Fetch all published pages from WP REST API."""
    api_base = wp_url.rstrip("/") + "/wp-json/wp/v2"
    all_pages = []
    page_num = 1

    while True:
        url = f"{api_base}/pages"
        params = {
            "per_page": 100, "page": page_num, "status": "publish",
            "_fields": "id,title,content,excerpt,slug,date,modified,featured_media,yoast_head_json",
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"  {C.RED}❌ Erreur API (batch {page_num}): {e}{C.RESET}")
            break

        pages = resp.json()
        if not pages:
            break
        all_pages.extend(pages)
        print(f"  {C.GREEN}📥{C.RESET} Batch {page_num}: {len(pages)} pages")

        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        if page_num >= total_pages:
            break
        page_num += 1

    return all_pages


# ── Interactive UI ───────────────────────────────────────────────

def print_header():
    print()
    print(f"  {C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════╗{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║  WordPress → PrestaShop Migration Tool  v2.0    ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║  Mode Interactif                                ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════╝{C.RESET}")
    print()


def print_separator(char="─", width=65):
    print(f"  {C.GRAY}{char * width}{C.RESET}")


def target_badge(target: str) -> str:
    if target == "cms":
        return C.badge("📄 CMS", C.BG_BLUE)
    elif target == "product":
        return C.badge("🏷️  PRODUIT", C.BG_MAGENTA)
    elif target == "skip":
        return C.badge("⏭️  IGNORÉ", C.BG_GRAY)
    return C.badge("❓ ???", C.BG_GRAY)


def display_page_list(pages: list[dict], assignments: dict[str, str]):
    """Display all pages with their current assignment."""
    print()
    print(f"  {C.BOLD}{C.WHITE}{'#':>4}  {'Destination':<16} {'Slug':<35} {'Titre':<30} {'Taille':>8} {'Img':>4}{C.RESET}")
    print_separator("─", 100)

    for i, page in enumerate(pages):
        slug = page.get("slug", "")
        title = _clean_title(page)[:30]
        size = _content_size(page)
        imgs = _image_count(page)
        target = assignments.get(slug, "skip")

        # Color coding
        if target == "cms":
            color = C.CYAN
            icon = "📄"
        elif target == "product":
            color = C.MAGENTA
            icon = "🏷️"
        elif target == "skip":
            color = C.GRAY
            icon = "⏭️"
        else:
            color = C.WHITE
            icon = "❓"

        num = f"{i + 1:>4}"
        dest = f"{icon} {target:<10}"
        print(f"  {C.DIM}{num}{C.RESET}  {color}{dest}{C.RESET}  {slug:<35} {title:<30} {C.DIM}{size:>8} {imgs:>4}{C.RESET}")

    print_separator("─", 100)
    cms_count = sum(1 for v in assignments.values() if v == "cms")
    prod_count = sum(1 for v in assignments.values() if v == "product")
    skip_count = sum(1 for v in assignments.values() if v == "skip")
    print(f"  {C.CYAN}📄 CMS: {cms_count}{C.RESET}  │  {C.MAGENTA}🏷️ Produit: {prod_count}{C.RESET}  │  {C.GRAY}⏭️ Ignoré: {skip_count}{C.RESET}  │  Total: {len(pages)}")
    print()


def get_page_indices(prompt: str, total: int) -> list[int]:
    """Parse user input for page selection. Supports: 1, 3-7, 1 3 5, all."""
    raw = input(prompt).strip().lower()
    if not raw:
        return []
    if raw == "all" or raw == "tout":
        return list(range(total))

    indices = []
    for part in re.split(r'[,\s]+', raw):
        if "-" in part:
            start, end = part.split("-", 1)
            try:
                s, e = int(start) - 1, int(end) - 1
                indices.extend(range(max(0, s), min(total, e + 1)))
            except ValueError:
                pass
        else:
            try:
                idx = int(part) - 1
                if 0 <= idx < total:
                    indices.append(idx)
            except ValueError:
                pass

    return sorted(set(indices))


def interactive_wizard(wp_url: str, config_path: str = "config.yaml") -> Optional[dict]:
    """
    Main interactive wizard. Returns the final assignments dict
    or None if the user cancels.
    """
    print_header()

    # ── Step 1: Scan WordPress ───────────────────────────────────
    print(f"  {C.BOLD}Étape 1/4 — Scan de {C.CYAN}{wp_url}{C.RESET}")
    print_separator()
    pages = fetch_all_pages(wp_url)

    if not pages:
        print(f"\n  {C.RED}❌ Aucune page trouvée. Vérifiez l'URL.{C.RESET}")
        return None

    pages.sort(key=lambda p: p.get("slug", ""))
    print(f"\n  {C.GREEN}✅ {len(pages)} pages trouvées{C.RESET}")
    print()

    # ── Step 2: Auto-categorize ──────────────────────────────────
    print(f"  {C.BOLD}Étape 2/4 — Catégorisation automatique{C.RESET}")
    print_separator()

    assignments: dict[str, str] = {}
    categories: dict[str, list[int]] = {
        "product": [], "content": [], "ambassador": [],
        "category": [], "other": [],
    }

    for i, page in enumerate(pages):
        slug = page.get("slug", "")
        title = _clean_title(page)
        cat = _auto_category(slug, title, page)
        categories[cat].append(i)

        # Default assignment based on category
        if cat == "product":
            assignments[slug] = "product"
        elif cat in ("content", "ambassador"):
            assignments[slug] = "cms"
        else:
            assignments[slug] = "skip"

    print(f"  Résultat de l'auto-détection :")
    print(f"    {C.MAGENTA}🏷️  Produits détectés:    {len(categories['product'])}{C.RESET}")
    print(f"    {C.CYAN}📄 Pages contenu:        {len(categories['content'])}{C.RESET}")
    print(f"    {C.CYAN}👤 Ambassadeurs:         {len(categories['ambassador'])}{C.RESET}")
    print(f"    {C.GRAY}📂 Pages catégorie:      {len(categories['category'])}{C.RESET}")
    print(f"    {C.GRAY}❓ Autres:               {len(categories['other'])}{C.RESET}")
    print()

    # ── Step 3: Interactive editing ──────────────────────────────
    print(f"  {C.BOLD}Étape 3/4 — Attribution des destinations{C.RESET}")
    print_separator()
    print(f"  {C.DIM}L'outil a pré-assigné les destinations. Vous pouvez les modifier.{C.RESET}")
    print()

    while True:
        display_page_list(pages, assignments)

        print(f"  {C.BOLD}Actions disponibles :{C.RESET}")
        print(f"    {C.CYAN}c <numéros>{C.RESET}  →  Mettre en Page CMS     (ex: c 1-5 8 12)")
        print(f"    {C.MAGENTA}p <numéros>{C.RESET}  →  Mettre en Produit       (ex: p 3 7-10)")
        print(f"    {C.GRAY}s <numéros>{C.RESET}  →  Ignorer                 (ex: s all)")
        print(f"    {C.YELLOW}v <numéro>{C.RESET}   →  Voir le détail d'une page")
        print(f"    {C.GREEN}ok{C.RESET}          →  Confirmer et continuer")
        print(f"    {C.RED}q{C.RESET}           →  Quitter")
        print()

        try:
            action = input(f"  {C.BOLD}> {C.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {C.YELLOW}Annulé.{C.RESET}")
            return None

        if not action:
            continue

        if action == "ok":
            break
        elif action == "q" or action == "quit":
            print(f"  {C.YELLOW}Annulé.{C.RESET}")
            return None

        elif action.startswith("v ") or action.startswith("v"):
            # View detail
            try:
                idx = int(action.split()[1]) - 1
                if 0 <= idx < len(pages):
                    _show_page_detail(pages[idx], assignments)
                else:
                    print(f"  {C.RED}Numéro invalide.{C.RESET}")
            except (ValueError, IndexError):
                print(f"  {C.RED}Usage: v <numéro>{C.RESET}")

        elif action[0] in ("c", "p", "s"):
            target_map = {"c": "cms", "p": "product", "s": "skip"}
            target = target_map[action[0]]
            indices = get_page_indices(f"", len(pages))

            # Parse the rest of the action string for indices
            rest = action[1:].strip()
            if rest:
                indices = []
                for part in re.split(r'[,\s]+', rest):
                    if "-" in part:
                        try:
                            s, e = part.split("-", 1)
                            indices.extend(range(max(0, int(s) - 1), min(len(pages), int(e))))
                        except ValueError:
                            pass
                    elif part.lower() in ("all", "tout"):
                        indices = list(range(len(pages)))
                        break
                    else:
                        try:
                            idx = int(part) - 1
                            if 0 <= idx < len(pages):
                                indices.append(idx)
                        except ValueError:
                            pass

            if indices:
                for idx in indices:
                    slug = pages[idx].get("slug", "")
                    assignments[slug] = target
                target_label = {"cms": "📄 CMS", "product": "🏷️ Produit", "skip": "⏭️ Ignoré"}[target]
                print(f"  {C.GREEN}✓ {len(indices)} page(s) → {target_label}{C.RESET}")
            else:
                print(f"  {C.RED}Aucune page sélectionnée. Usage: {action[0]} 1-5 8 12{C.RESET}")

        else:
            print(f"  {C.RED}Commande inconnue. Tapez 'ok' pour confirmer ou 'q' pour quitter.{C.RESET}")

    # ── Step 4: Save & confirm ───────────────────────────────────
    print()
    print(f"  {C.BOLD}Étape 4/4 — Sauvegarde{C.RESET}")
    print_separator()

    # Group by target for config
    cms_slugs = [s for s, t in assignments.items() if t == "cms"]
    product_slugs = [s for s, t in assignments.items() if t == "product"]
    skip_slugs = [s for s, t in assignments.items() if t == "skip"]

    print(f"  Résumé final :")
    print(f"    {C.CYAN}📄 Pages CMS:    {len(cms_slugs)}{C.RESET}")
    print(f"    {C.MAGENTA}🏷️ Produits:     {len(product_slugs)}{C.RESET}")
    print(f"    {C.GRAY}⏭️ Ignorées:     {len(skip_slugs)}{C.RESET}")
    print()

    # Save mapping to YAML
    mapping = {
        "mapping": {
            "default": "skip",
            "rules": [],
        }
    }

    if cms_slugs:
        mapping["mapping"]["rules"].append({
            "name": "cms_pages",
            "target": "cms",
            "cms_category_id": 1,
            "slugs": sorted(cms_slugs),
        })

    if product_slugs:
        mapping["mapping"]["rules"].append({
            "name": "products",
            "target": "product",
            "match_by": "name",
            "slugs": sorted(product_slugs),
        })

    if skip_slugs:
        mapping["mapping"]["rules"].append({
            "name": "skipped",
            "target": "skip",
            "slugs": sorted(skip_slugs),
        })

    # Save or merge with existing config
    mapping_file = "mapping.yaml"
    try:
        with open(mapping_file, "w", encoding="utf-8") as f:
            yaml.dump(mapping, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  {C.GREEN}✅ Mapping sauvegardé → {mapping_file}{C.RESET}")
    except Exception as e:
        print(f"  {C.RED}❌ Erreur sauvegarde: {e}{C.RESET}")

    # Also try to merge into existing config.yaml
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
            existing["mapping"] = mapping["mapping"]
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            print(f"  {C.GREEN}✅ Mapping intégré dans → {config_path}{C.RESET}")
        except Exception as e:
            print(f"  {C.YELLOW}⚠️ Config existant non modifié: {e}{C.RESET}")
    else:
        print(f"  {C.DIM}ℹ️ Pas de {config_path} trouvé. Utilisez mapping.yaml comme référence.{C.RESET}")

    print()

    # Ask if user wants to proceed with migration
    print(f"  {C.BOLD}Prêt à lancer la migration ?{C.RESET}")
    print(f"    {C.GREEN}y{C.RESET}  →  Lancer maintenant (dry-run)")
    print(f"    {C.CYAN}Y{C.RESET}  →  Lancer maintenant (LIVE)")
    print(f"    {C.RED}n{C.RESET}  →  Quitter (le mapping est sauvegardé)")
    print()

    try:
        choice = input(f"  {C.BOLD}> {C.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "n"

    return {
        "assignments": assignments,
        "run_migration": choice in ("y", "Y"),
        "dry_run": choice != "Y",
        "config_path": config_path,
        "mapping": mapping,
    }


def _show_page_detail(page: dict, assignments: dict):
    """Show detailed info about a single page."""
    slug = page.get("slug", "")
    title = _clean_title(page)
    content_html = page.get("content", {}).get("rendered", "")
    yoast = page.get("yoast_head_json", {}) or {}
    imgs = _image_count(page)
    size = _content_size(page)
    target = assignments.get(slug, "?")

    # Text preview
    text = re.sub(r'<[^>]+>', ' ', content_html)
    text = re.sub(r'\s+', ' ', text).strip()
    text = html.unescape(text)[:400]

    print()
    print_separator("═", 65)
    print(f"  {C.BOLD}{title}{C.RESET}")
    print_separator("─", 65)
    print(f"  Slug:          {C.CYAN}{slug}{C.RESET}")
    print(f"  Destination:   {target_badge(target)}")
    print(f"  Taille:        {size}")
    print(f"  Images:        {imgs}")
    print(f"  Meta Title:    {C.DIM}{yoast.get('title', 'N/A')}{C.RESET}")
    print(f"  Meta Desc:     {C.DIM}{(yoast.get('description', '') or 'N/A')[:100]}{C.RESET}")
    print(f"  Modifié:       {page.get('modified', 'N/A')[:10]}")

    # Content warnings
    has_divi = bool(re.search(r'et_pb_', content_html, re.I))
    has_forms = bool(re.search(r'wpcf7', content_html, re.I))
    has_tables = bool(re.search(r'<table|wptb-', content_html, re.I))

    if has_divi or has_forms or has_tables:
        print(f"  {C.YELLOW}Alertes:{C.RESET}", end="")
        if has_divi:
            print(f" [Divi]", end="")
        if has_forms:
            print(f" [Formulaire]", end="")
        if has_tables:
            print(f" [Tableaux]", end="")
        print()

    print(f"\n  {C.DIM}Aperçu:{C.RESET}")
    # Wrap text nicely
    words = text.split()
    line = "  "
    for word in words:
        if len(line) + len(word) + 1 > 70:
            print(f"  {C.DIM}{line}{C.RESET}")
            line = "  "
        line += word + " "
    if line.strip():
        print(f"  {C.DIM}{line}{C.RESET}")

    print_separator("═", 65)
    print()


# ── Entry point ──────────────────────────────────────────────────

def run_interactive(wp_url: str = None, config_path: str = "config.yaml"):
    """Main entry point for interactive mode."""
    if not wp_url:
        print_header()
        try:
            wp_url = input(f"  {C.BOLD}URL WordPress : {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {C.YELLOW}Annulé.{C.RESET}")
            return

        if not wp_url:
            print(f"  {C.RED}URL requise.{C.RESET}")
            return

    if not wp_url.startswith("http"):
        wp_url = "https://" + wp_url

    result = interactive_wizard(wp_url, config_path)

    if result and result.get("run_migration"):
        print()
        print(f"  {C.BOLD}{C.GREEN}🚀 Lancement de la migration...{C.RESET}")
        print_separator()

        # Import and run migrator with the saved config
        try:
            from .config import load_config
            from .migrator import Migrator
            from .utils import setup_logging

            config = load_config(result["config_path"])
            config.migration.dry_run = result.get("dry_run", True)

            logger = setup_logging(
                log_file=config.migration.log_file,
                verbose=True,
            )

            migrator = Migrator(config)
            migrator.run()
        except FileNotFoundError:
            print(f"\n  {C.YELLOW}⚠️ Fichier config non trouvé.")
            print(f"  Créez {config_path} avec vos identifiants PrestaShop.{C.RESET}")
            print(f"  Le mapping a été sauvegardé dans mapping.yaml")
        except Exception as e:
            print(f"\n  {C.RED}❌ Erreur: {e}{C.RESET}")
    else:
        print(f"\n  {C.DIM}Le mapping a été sauvegardé. Relancez quand prêt.{C.RESET}")
        print()


if __name__ == "__main__":
    run_interactive()
