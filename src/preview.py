#!/usr/bin/env python3
"""
Preview mode: fetch WordPress pages, transform them, and generate
an HTML report showing exactly what would be pushed to PrestaShop.

Usage:
    python -m src.preview --url https://www.korteldesign.com
    python -m src.preview --url https://www.korteldesign.com --output preview.html
"""

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# ──────────────────────────────────────────────────────────────────
# Mini-transformer (standalone, no config needed)
# ──────────────────────────────────────────────────────────────────

WP_CLASSES_RE = re.compile(
    r'\b(wp-block-[a-z0-9-]+|has-[a-z0-9-]+|is-layout-[a-z]+|'
    r'alignwide|alignfull|wp-image-\d+|et_pb_[a-z0-9_]+|'
    r'cl-ib[a-z0-9_-]*|cl_custom_css_\d+|wptb-[a-z0-9_-]+|'
    r'dvppl_[a-z0-9_]+|wpcf7[a-z0-9_-]*)\b',
    re.IGNORECASE,
)


def clean_classes(html_content: str) -> str:
    """Remove WordPress-specific CSS classes."""
    def _replace(m):
        return ''
    return WP_CLASSES_RE.sub(_replace, html_content)


def count_images(html_content: str) -> list[str]:
    """Extract image URLs from content."""
    return re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.I)


def extract_text_preview(html_content: str, max_len: int = 300) -> str:
    """Strip HTML tags and return a text preview."""
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    text = html.unescape(text)
    if len(text) > max_len:
        text = text[:max_len] + '…'
    return text


def sanitize_slug(slug: str) -> str:
    """Basic slug sanitization for PrestaShop."""
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:128]


def content_size_human(content: str) -> str:
    """Return human-readable size of content."""
    size = len(content.encode('utf-8'))
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


# ──────────────────────────────────────────────────────────────────
# WordPress API fetcher
# ──────────────────────────────────────────────────────────────────

def fetch_pages(base_url: str) -> list[dict[str, Any]]:
    """Fetch all published pages from the WP REST API."""
    api_base = base_url.rstrip('/') + '/wp-json/wp/v2'
    all_pages = []
    page_num = 1

    while True:
        url = f"{api_base}/pages"
        params = {
            'per_page': 100,
            'page': page_num,
            'status': 'publish',
            '_fields': 'id,title,content,excerpt,slug,date,modified,featured_media,yoast_head_json',
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"  ❌ API error (page {page_num}): {e}", file=sys.stderr)
            break

        pages = resp.json()
        if not pages:
            break

        all_pages.extend(pages)
        print(f"  📥 Fetched batch {page_num}: {len(pages)} pages")

        total_pages = int(resp.headers.get('X-WP-TotalPages', 1))
        if page_num >= total_pages:
            break
        page_num += 1

    return all_pages


# ──────────────────────────────────────────────────────────────────
# Page analysis
# ──────────────────────────────────────────────────────────────────

def analyze_page(page: dict) -> dict:
    """Analyze a single WP page and return structured preview data."""
    title = html.unescape(page.get('title', {}).get('rendered', '(sans titre)'))
    content_html = page.get('content', {}).get('rendered', '')
    slug = page.get('slug', '')
    excerpt_html = page.get('excerpt', {}).get('rendered', '')

    # SEO data (Yoast)
    yoast = page.get('yoast_head_json', {}) or {}
    meta_title = yoast.get('title', title)
    meta_desc = yoast.get('description', '')

    # Image analysis
    images = count_images(content_html)

    # Content analysis
    has_forms = bool(re.search(r'wpcf7|contact-form', content_html, re.I))
    has_shortcodes = bool(re.search(r'\[/?[a-z_]+', content_html))
    has_tables = bool(re.search(r'<table|wptb-', content_html, re.I))
    has_divi = bool(re.search(r'et_pb_|et_builder', content_html, re.I))

    # Warnings
    warnings = []
    if has_forms:
        warnings.append('⚠️ Contient un formulaire (Contact Form 7) — ne sera pas fonctionnel')
    if has_shortcodes:
        warnings.append('⚠️ Contient des shortcodes WP — rendus bruts possible')
    if has_divi:
        warnings.append('⚠️ Contient du markup Divi — mise en page complexe')
    if has_tables:
        warnings.append('⚠️ Contient des tableaux WP — structure lourde')
    if len(content_html) > 100_000:
        warnings.append(f'⚠️ Contenu très volumineux ({content_size_human(content_html)})')
    if not content_html.strip():
        warnings.append('ℹ️ Page vide (pas de contenu)')

    return {
        'wp_id': page.get('id', 0),
        'title': title,
        'slug': slug,
        'ps_slug': sanitize_slug(slug),
        'meta_title': html.unescape(meta_title) if meta_title else '',
        'meta_description': html.unescape(meta_desc)[:512] if meta_desc else '',
        'content_size': content_size_human(content_html),
        'content_preview': extract_text_preview(content_html),
        'image_count': len(images),
        'image_urls': images[:5],  # first 5 for preview
        'warnings': warnings,
        'date': page.get('date', ''),
        'modified': page.get('modified', ''),
        'has_seo': bool(meta_title or meta_desc),
    }


# ──────────────────────────────────────────────────────────────────
# HTML report generator
# ──────────────────────────────────────────────────────────────────

def generate_html_report(pages: list[dict], wp_url: str) -> str:
    """Generate a beautiful HTML preview report."""
    total_images = sum(p['image_count'] for p in pages)
    pages_with_warnings = sum(1 for p in pages if p['warnings'])
    pages_with_seo = sum(1 for p in pages if p['has_seo'])

    rows = ''
    detail_cards = ''

    for i, p in enumerate(pages):
        badge_class = 'badge-ok' if not p['warnings'] else 'badge-warn'
        badge_text = '✅ OK' if not p['warnings'] else f'⚠️ {len(p["warnings"])} alert(s)'

        rows += f'''
        <tr onclick="document.getElementById('detail-{i}').scrollIntoView({{behavior:'smooth'}})" style="cursor:pointer">
            <td><code>{p['slug']}</code></td>
            <td><strong>{html.escape(p['title'])}</strong></td>
            <td class="center">{p['content_size']}</td>
            <td class="center">{p['image_count']}</td>
            <td class="center">{'✅' if p['has_seo'] else '❌'}</td>
            <td class="center"><span class="{badge_class}">{badge_text}</span></td>
        </tr>'''

        warnings_html = ''
        if p['warnings']:
            warnings_html = '<div class="warnings">' + '<br>'.join(p['warnings']) + '</div>'

        images_html = ''
        if p['image_urls']:
            thumbs = ''.join(
                f'<img src="{url}" class="thumb" loading="lazy" onerror="this.style.display=\'none\'">'
                for url in p['image_urls']
            )
            images_html = f'<div class="thumbs">{thumbs}</div>'
            if p['image_count'] > 5:
                images_html += f'<p class="text-muted">+ {p["image_count"] - 5} autres images</p>'

        detail_cards += f'''
        <div class="card" id="detail-{i}">
            <div class="card-header">
                <h3>{html.escape(p['title'])}</h3>
                <span class="slug">→ PrestaShop slug: <code>{p['ps_slug']}</code></span>
            </div>
            <div class="card-body">
                <table class="meta-table">
                    <tr><td>WP ID</td><td>{p['wp_id']}</td></tr>
                    <tr><td>Slug WP</td><td><code>{p['slug']}</code></td></tr>
                    <tr><td>Meta Title</td><td>{html.escape(p['meta_title']) or '<em>vide</em>'}</td></tr>
                    <tr><td>Meta Description</td><td>{html.escape(p['meta_description']) or '<em>vide</em>'}</td></tr>
                    <tr><td>Taille contenu</td><td>{p['content_size']}</td></tr>
                    <tr><td>Images</td><td>{p['image_count']}</td></tr>
                    <tr><td>Dernière modif.</td><td>{p['modified'][:10] if p['modified'] else 'N/A'}</td></tr>
                </table>
                {warnings_html}
                <div class="content-preview">
                    <strong>Aperçu du contenu :</strong>
                    <p>{html.escape(p['content_preview']) or '<em>Aucun contenu textuel</em>'}</p>
                </div>
                {images_html}
            </div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Preview Migration — {html.escape(wp_url)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f23;
            color: #e0e0e0;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{
            font-size: 2em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        h2 {{ color: #667eea; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .stat {{
            background: #1a1a3e;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        .stat-value {{ font-size: 2.5em; font-weight: 700; color: #667eea; }}
        .stat-label {{ font-size: 0.85em; color: #888; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid #222;
        }}
        th {{ background: #1a1a3e; color: #667eea; font-weight: 600; position: sticky; top: 0; }}
        tr:hover {{ background: #1a1a3e; }}
        .center {{ text-align: center; }}
        code {{ background: #1a1a3e; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: #a0cfff; }}
        .badge-ok {{ background: #1a3a1a; color: #4caf50; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .badge-warn {{ background: #3a2a0a; color: #ffa726; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .card {{
            background: #1a1a3e;
            border: 1px solid #333;
            border-radius: 12px;
            margin: 15px 0;
            overflow: hidden;
        }}
        .card-header {{
            background: linear-gradient(135deg, #1a1a3e 0%, #252560 100%);
            padding: 15px 20px;
            border-bottom: 1px solid #333;
        }}
        .card-header h3 {{ color: #e0e0e0; font-size: 1.2em; }}
        .slug {{ color: #888; font-size: 0.85em; }}
        .card-body {{ padding: 15px 20px; }}
        .meta-table {{ margin: 0; }}
        .meta-table td:first-child {{ font-weight: 600; color: #667eea; width: 160px; }}
        .warnings {{
            background: #3a2a0a;
            border-left: 3px solid #ffa726;
            padding: 10px 15px;
            margin: 12px 0;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .content-preview {{
            background: #12122e;
            padding: 12px 15px;
            margin: 12px 0;
            border-radius: 8px;
            font-size: 0.9em;
        }}
        .content-preview p {{ color: #aaa; margin-top: 5px; }}
        .thumbs {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }}
        .thumb {{
            width: 120px; height: 80px;
            object-fit: cover;
            border-radius: 6px;
            border: 1px solid #333;
        }}
        .text-muted {{ color: #666; font-size: 0.85em; }}
        .footer {{ text-align: center; color: #555; margin: 40px 0 20px; font-size: 0.85em; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🔍 Preview Migration WordPress → PrestaShop</h1>
    <p class="subtitle">Source : <strong>{html.escape(wp_url)}</strong> — Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>

    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(pages)}</div>
            <div class="stat-label">Pages à migrer</div>
        </div>
        <div class="stat">
            <div class="stat-value">{total_images}</div>
            <div class="stat-label">Images détectées</div>
        </div>
        <div class="stat">
            <div class="stat-value">{pages_with_seo}</div>
            <div class="stat-label">Pages avec SEO</div>
        </div>
        <div class="stat">
            <div class="stat-value">{pages_with_warnings}</div>
            <div class="stat-label">Pages avec alertes</div>
        </div>
    </div>

    <h2>📋 Vue d'ensemble</h2>
    <table>
        <thead>
            <tr>
                <th>Slug</th>
                <th>Titre</th>
                <th class="center">Taille</th>
                <th class="center">Images</th>
                <th class="center">SEO</th>
                <th class="center">Statut</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>

    <h2>📄 Détail par page</h2>
    {detail_cards}

    <p class="footer">
        Migration Tool — WP → PrestaShop — Mode Preview<br>
        Cliquez sur une ligne du tableau pour naviguer vers les détails
    </p>
</div>
</body>
</html>'''


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Preview WordPress content before migration to PrestaShop.'
    )
    parser.add_argument(
        '--url', '-u', required=True,
        help='WordPress site URL (e.g. https://www.korteldesign.com)',
    )
    parser.add_argument(
        '--output', '-o', default='preview.html',
        help='Output HTML file (default: preview.html)',
    )
    parser.add_argument(
        '--json', action='store_true',
        help='Also output raw analysis as JSON',
    )
    args = parser.parse_args()

    wp_url = args.url.rstrip('/')
    print(f"\n🌐 Connexion à {wp_url} ...")

    # Fetch
    raw_pages = fetch_pages(wp_url)
    if not raw_pages:
        print("❌ Aucune page trouvée. Vérifiez l'URL et que l'API REST est accessible.")
        sys.exit(1)

    print(f"\n📊 Analyse de {len(raw_pages)} pages ...")

    # Analyze
    analyzed = [analyze_page(p) for p in raw_pages]
    analyzed.sort(key=lambda p: p['slug'])

    # Console summary
    print(f"\n{'='*60}")
    print(f"  📋 RÉSUMÉ PREVIEW — {wp_url}")
    print(f"{'='*60}")
    print(f"  📄 Pages trouvées:      {len(analyzed)}")
    print(f"  🖼️  Images détectées:    {sum(p['image_count'] for p in analyzed)}")
    print(f"  🔍 Pages avec SEO:      {sum(1 for p in analyzed if p['has_seo'])}")
    print(f"  ⚠️  Pages avec alertes:  {sum(1 for p in analyzed if p['warnings'])}")
    print(f"{'='*60}\n")

    # List pages
    for p in analyzed:
        status = '✅' if not p['warnings'] else '⚠️'
        print(f"  {status} {p['slug']:<35} {p['title']:<30} [{p['content_size']}] [{p['image_count']} img]")

    # HTML report
    html_report = generate_html_report(analyzed, wp_url)
    output_path = Path(args.output)
    output_path.write_text(html_report, encoding='utf-8')
    print(f"\n✅ Rapport HTML → {output_path.resolve()}")

    # Optional JSON
    if args.json:
        json_path = output_path.with_suffix('.json')
        json_path.write_text(json.dumps(analyzed, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"✅ Données JSON → {json_path.resolve()}")

    print(f"\n💡 Ouvrez {output_path} dans votre navigateur pour la preview complète.")


if __name__ == '__main__':
    main()
