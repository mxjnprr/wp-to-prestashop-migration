#!/usr/bin/env python3
"""
Preview mode: fetch WordPress pages, optionally apply routing rules,
and generate an HTML report showing what would go where in PrestaShop.

Usage:
    # Without config (scans everything, no routing):
    python -m src.preview --url https://www.korteldesign.com

    # With config (shows routing destinations):
    python -m src.preview --url https://www.korteldesign.com --config config.yaml
"""

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

# ──────────────────────────────────────────────────────────────────
# Mini-transformer (standalone, no heavy deps)
# ──────────────────────────────────────────────────────────────────

WP_CLASSES_RE = re.compile(
    r'\b(wp-block-[a-z0-9-]+|has-[a-z0-9-]+|is-layout-[a-z]+|'
    r'alignwide|alignfull|wp-image-\d+|et_pb_[a-z0-9_]+|'
    r'cl-ib[a-z0-9_-]*|cl_custom_css_\d+|wptb-[a-z0-9_-]+|'
    r'dvppl_[a-z0-9_]+|wpcf7[a-z0-9_-]*)\b',
    re.IGNORECASE,
)


def count_images(html_content: str) -> list[str]:
    return re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.I)


def extract_text_preview(html_content: str, max_len: int = 300) -> str:
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    text = html.unescape(text)
    return text[:max_len] + '…' if len(text) > max_len else text


def sanitize_slug(slug: str) -> str:
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:128]


def content_size_human(content: str) -> str:
    size = len(content.encode('utf-8'))
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# ──────────────────────────────────────────────────────────────────
# WordPress API fetcher
# ──────────────────────────────────────────────────────────────────

def fetch_pages(base_url: str) -> list[dict[str, Any]]:
    api_base = base_url.rstrip('/') + '/wp-json/wp/v2'
    all_pages = []
    page_num = 1

    while True:
        url = f"{api_base}/pages"
        params = {
            'per_page': 100, 'page': page_num, 'status': 'publish',
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

def analyze_page(page: dict, route: Optional[dict] = None) -> dict:
    title = html.unescape(page.get('title', {}).get('rendered', '(sans titre)'))
    content_html = page.get('content', {}).get('rendered', '')
    slug = page.get('slug', '')
    yoast = page.get('yoast_head_json', {}) or {}
    meta_title = yoast.get('title', title)
    meta_desc = yoast.get('description', '')
    images = count_images(content_html)

    has_forms = bool(re.search(r'wpcf7|contact-form', content_html, re.I))
    has_shortcodes = bool(re.search(r'\[/?[a-z_]+', content_html))
    has_tables = bool(re.search(r'<table|wptb-', content_html, re.I))
    has_divi = bool(re.search(r'et_pb_|et_builder', content_html, re.I))

    warnings = []
    if has_forms:
        warnings.append('⚠️ Formulaire (CF7) — non fonctionnel')
    if has_shortcodes:
        warnings.append('⚠️ Shortcodes WP')
    if has_divi:
        warnings.append('⚠️ Markup Divi')
    if has_tables:
        warnings.append('⚠️ Tableaux WP')
    if len(content_html) > 100_000:
        warnings.append(f'⚠️ Volumineux ({content_size_human(content_html)})')
    if not content_html.strip():
        warnings.append('ℹ️ Page vide')

    result = {
        'wp_id': page.get('id', 0),
        'title': title,
        'slug': slug,
        'ps_slug': sanitize_slug(slug),
        'meta_title': html.unescape(meta_title) if meta_title else '',
        'meta_description': html.unescape(meta_desc)[:512] if meta_desc else '',
        'content_size': content_size_human(content_html),
        'content_preview': extract_text_preview(content_html),
        'image_count': len(images),
        'image_urls': images[:5],
        'warnings': warnings,
        'date': page.get('date', ''),
        'modified': page.get('modified', ''),
        'has_seo': bool(meta_title or meta_desc),
    }

    # Routing info (if config provided)
    if route:
        result['target'] = route.get('target', '?')
        result['rule_name'] = route.get('rule_name', '')
        result['cms_category_id'] = route.get('cms_category_id')
    else:
        result['target'] = 'unrouted'
        result['rule_name'] = ''
        result['cms_category_id'] = None

    return result


# ──────────────────────────────────────────────────────────────────
# HTML report generator
# ──────────────────────────────────────────────────────────────────

TARGET_ICONS = {
    'cms': ('📄', 'Page CMS', 'badge-cms'),
    'product': ('🏷️', 'Produit', 'badge-product'),
    'skip': ('⏭️', 'Ignoré', 'badge-skip'),
    'unrouted': ('❓', 'Non routé', 'badge-unrouted'),
}


def generate_html_report(pages: list[dict], wp_url: str, has_routing: bool = False) -> str:
    total_images = sum(p['image_count'] for p in pages)
    pages_with_warnings = sum(1 for p in pages if p['warnings'])
    pages_with_seo = sum(1 for p in pages if p['has_seo'])

    # Routing stats
    cms_count = sum(1 for p in pages if p.get('target') == 'cms')
    product_count = sum(1 for p in pages if p.get('target') == 'product')
    skip_count = sum(1 for p in pages if p.get('target') == 'skip')

    rows = ''
    detail_cards = ''

    for i, p in enumerate(pages):
        # Target badge
        icon, label, badge_cls = TARGET_ICONS.get(
            p.get('target', 'unrouted'),
            ('❓', '?', 'badge-unrouted')
        )
        target_badge = f'<span class="{badge_cls}">{icon} {label}</span>'

        # Warning badge
        w_badge_class = 'badge-ok' if not p['warnings'] else 'badge-warn'
        w_badge_text = '✅' if not p['warnings'] else f'⚠️ {len(p["warnings"])}'

        target_col = f'<td class="center">{target_badge}</td>' if has_routing else ''
        rule_info = f' <span class="rule-name">({p["rule_name"]})</span>' if p.get('rule_name') else ''

        rows += f'''
        <tr onclick="document.getElementById('detail-{i}').scrollIntoView({{behavior:'smooth'}})" style="cursor:pointer">
            {target_col}
            <td><code>{p['slug']}</code></td>
            <td><strong>{html.escape(p['title'])}</strong></td>
            <td class="center">{p['content_size']}</td>
            <td class="center">{p['image_count']}</td>
            <td class="center">{'✅' if p['has_seo'] else '❌'}</td>
            <td class="center"><span class="{w_badge_class}">{w_badge_text}</span></td>
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

        target_row = f'<tr><td>Destination</td><td>{target_badge}{rule_info}</td></tr>' if has_routing else ''

        detail_cards += f'''
        <div class="card target-{p.get('target', 'unrouted')}" id="detail-{i}">
            <div class="card-header">
                <h3>{html.escape(p['title'])}</h3>
                <span class="slug">→ PrestaShop: <code>{p['ps_slug']}</code></span>
            </div>
            <div class="card-body">
                <table class="meta-table">
                    {target_row}
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
                    <strong>Aperçu :</strong>
                    <p>{html.escape(p['content_preview']) or '<em>Aucun contenu</em>'}</p>
                </div>
                {images_html}
            </div>
        </div>'''

    # Routing stats block
    routing_stats = ''
    if has_routing:
        routing_stats = f'''
        <div class="stat">
            <div class="stat-value stat-cms">{cms_count}</div>
            <div class="stat-label">→ Pages CMS</div>
        </div>
        <div class="stat">
            <div class="stat-value stat-product">{product_count}</div>
            <div class="stat-label">→ Produits</div>
        </div>
        <div class="stat">
            <div class="stat-value stat-skip">{skip_count}</div>
            <div class="stat-label">→ Ignorées</div>
        </div>'''

    target_header = '<th class="center">Destination</th>' if has_routing else ''

    # Filter buttons
    filter_buttons = ''
    if has_routing:
        filter_buttons = '''
        <div class="filters">
            <button class="filter-btn active" onclick="filterPages('all')">Tout</button>
            <button class="filter-btn filter-cms" onclick="filterPages('cms')">📄 CMS</button>
            <button class="filter-btn filter-product" onclick="filterPages('product')">🏷️ Produits</button>
            <button class="filter-btn filter-skip" onclick="filterPages('skip')">⏭️ Ignorées</button>
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
            background: #0f0f23; color: #e0e0e0; line-height: 1.6;
        }}
        .container {{ max-width: 1300px; margin: 0 auto; padding: 20px; }}
        h1 {{
            font-size: 2em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        h2 {{ color: #667eea; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        .stats {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px; margin-bottom: 30px;
        }}
        .stat {{
            background: #1a1a3e; border: 1px solid #333; border-radius: 12px;
            padding: 20px; text-align: center;
        }}
        .stat-value {{ font-size: 2.2em; font-weight: 700; color: #667eea; }}
        .stat-cms {{ color: #4fc3f7; }}
        .stat-product {{ color: #ab47bc; }}
        .stat-skip {{ color: #78909c; }}
        .stat-label {{ font-size: 0.85em; color: #888; margin-top: 5px; }}
        .filters {{ margin: 15px 0; display: flex; gap: 8px; }}
        .filter-btn {{
            padding: 8px 16px; border-radius: 20px; border: 1px solid #444;
            background: #1a1a3e; color: #ccc; cursor: pointer; font-size: 0.9em;
            transition: all 0.2s;
        }}
        .filter-btn:hover {{ background: #252560; }}
        .filter-btn.active {{ background: #667eea; color: white; border-color: #667eea; }}
        .filter-cms.active {{ background: #0277bd; border-color: #0277bd; }}
        .filter-product.active {{ background: #7b1fa2; border-color: #7b1fa2; }}
        .filter-skip.active {{ background: #455a64; border-color: #455a64; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #222; }}
        th {{ background: #1a1a3e; color: #667eea; font-weight: 600; position: sticky; top: 0; z-index: 10; }}
        tr:hover {{ background: #1a1a3e; }}
        .center {{ text-align: center; }}
        code {{ background: #1a1a3e; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: #a0cfff; }}
        .badge-ok {{ background: #1a3a1a; color: #4caf50; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .badge-warn {{ background: #3a2a0a; color: #ffa726; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .badge-cms {{ background: #0d2137; color: #4fc3f7; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .badge-product {{ background: #2a0d37; color: #ce93d8; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .badge-skip {{ background: #1a1a1a; color: #78909c; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .badge-unrouted {{ background: #3a3a0a; color: #ffd54f; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }}
        .rule-name {{ color: #666; font-size: 0.8em; margin-left: 5px; }}
        .card {{
            background: #1a1a3e; border: 1px solid #333; border-radius: 12px;
            margin: 15px 0; overflow: hidden;
        }}
        .card.target-skip {{ opacity: 0.5; }}
        .card.target-cms {{ border-left: 3px solid #4fc3f7; }}
        .card.target-product {{ border-left: 3px solid #ce93d8; }}
        .card-header {{
            background: linear-gradient(135deg, #1a1a3e 0%, #252560 100%);
            padding: 15px 20px; border-bottom: 1px solid #333;
        }}
        .card-header h3 {{ color: #e0e0e0; font-size: 1.2em; }}
        .slug {{ color: #888; font-size: 0.85em; }}
        .card-body {{ padding: 15px 20px; }}
        .meta-table {{ margin: 0; }}
        .meta-table td:first-child {{ font-weight: 600; color: #667eea; width: 160px; }}
        .warnings {{
            background: #3a2a0a; border-left: 3px solid #ffa726;
            padding: 10px 15px; margin: 12px 0; border-radius: 4px; font-size: 0.9em;
        }}
        .content-preview {{
            background: #12122e; padding: 12px 15px; margin: 12px 0; border-radius: 8px; font-size: 0.9em;
        }}
        .content-preview p {{ color: #aaa; margin-top: 5px; }}
        .thumbs {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }}
        .thumb {{ width: 120px; height: 80px; object-fit: cover; border-radius: 6px; border: 1px solid #333; }}
        .text-muted {{ color: #666; font-size: 0.85em; }}
        .hidden {{ display: none !important; }}
        .footer {{ text-align: center; color: #555; margin: 40px 0 20px; font-size: 0.85em; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🔍 Preview Migration WordPress → PrestaShop</h1>
    <p class="subtitle">
        Source : <strong>{html.escape(wp_url)}</strong> — Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        {' — <strong>avec routing</strong>' if has_routing else ' — <em>sans config (scan complet)</em>'}
    </p>

    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(pages)}</div>
            <div class="stat-label">Pages WP</div>
        </div>
        <div class="stat">
            <div class="stat-value">{total_images}</div>
            <div class="stat-label">Images</div>
        </div>
        <div class="stat">
            <div class="stat-value">{pages_with_seo}</div>
            <div class="stat-label">Avec SEO</div>
        </div>
        {routing_stats}
        <div class="stat">
            <div class="stat-value">{pages_with_warnings}</div>
            <div class="stat-label">Alertes</div>
        </div>
    </div>

    {filter_buttons}

    <h2>📋 Vue d'ensemble</h2>
    <table id="overview-table">
        <thead>
            <tr>
                {target_header}
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
        Migration Tool WP → PrestaShop — Preview<br>
        Cliquez sur une ligne pour naviguer aux détails
    </p>
</div>

<script>
function filterPages(target) {{
    // Update buttons
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    // Filter table rows
    const rows = document.querySelectorAll('#overview-table tbody tr');
    rows.forEach(row => {{
        if (target === 'all') {{
            row.classList.remove('hidden');
        }} else {{
            const badge = row.querySelector('[class*="badge-"]');
            const classes = badge ? badge.className : '';
            if (classes.includes('badge-' + target)) {{
                row.classList.remove('hidden');
            }} else {{
                row.classList.add('hidden');
            }}
        }}
    }});

    // Filter detail cards
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {{
        if (target === 'all') {{
            card.classList.remove('hidden');
        }} else if (card.classList.contains('target-' + target)) {{
            card.classList.remove('hidden');
        }} else {{
            card.classList.add('hidden');
        }}
    }});
}}
</script>
</body>
</html>'''


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Preview WordPress content before migration to PrestaShop.'
    )
    parser.add_argument('--url', '-u', required=True, help='WordPress site URL')
    parser.add_argument('--output', '-o', default='preview.html', help='Output HTML file')
    parser.add_argument('--json', action='store_true', help='Also output raw JSON')
    parser.add_argument(
        '--config', '-c', default=None,
        help='Config file with mapping rules (enables routing preview)',
    )
    args = parser.parse_args()

    wp_url = args.url.rstrip('/')
    has_routing = False
    router = None

    # Load routing config if provided
    if args.config:
        try:
            import yaml
            from .router import build_router_from_config
            with open(args.config, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            mapping_config = raw_config.get('mapping', {})
            if mapping_config.get('rules'):
                router = build_router_from_config(mapping_config)
                has_routing = True
                summary = router.get_summary()
                print(f"  📐 Routing: {summary['total_rules']} rules loaded, default={summary['default']}")
            else:
                print("  ℹ️ Config trouvé mais pas de règles de mapping — scan complet")
        except Exception as e:
            print(f"  ⚠️ Could not load config: {e} — continuing without routing")

    print(f"\n🌐 Connexion à {wp_url} ...")
    raw_pages = fetch_pages(wp_url)
    if not raw_pages:
        print("❌ Aucune page trouvée.")
        sys.exit(1)

    print(f"\n📊 Analyse de {len(raw_pages)} pages ...")

    analyzed = []
    for p in raw_pages:
        slug = p.get('slug', '')
        title = html.unescape(p.get('title', {}).get('rendered', ''))
        route_info = None
        if router:
            route = router.route(slug, title)
            route_info = {
                'target': route.target,
                'rule_name': route.rule_name,
                'cms_category_id': route.cms_category_id,
            }
        analyzed.append(analyze_page(p, route_info))

    analyzed.sort(key=lambda p: (
        {'product': 0, 'cms': 1, 'skip': 2, 'unrouted': 3}.get(p.get('target', 'unrouted'), 4),
        p['slug']
    ))

    # Console
    print(f"\n{'='*65}")
    print(f"  📋 RÉSUMÉ — {wp_url}")
    print(f"{'='*65}")
    print(f"  📄 Pages totales:      {len(analyzed)}")
    if has_routing:
        print(f"  🏷️  → Produits PS:     {sum(1 for p in analyzed if p.get('target') == 'product')}")
        print(f"  📄 → Pages CMS:       {sum(1 for p in analyzed if p.get('target') == 'cms')}")
        print(f"  ⏭️  → Ignorées:        {sum(1 for p in analyzed if p.get('target') == 'skip')}")
    print(f"  🖼️  Images:            {sum(p['image_count'] for p in analyzed)}")
    print(f"  🔍 SEO:               {sum(1 for p in analyzed if p['has_seo'])}")
    print(f"{'='*65}\n")

    for p in analyzed:
        icon = {'cms': '📄', 'product': '🏷️', 'skip': '⏭️'}.get(p.get('target', ''), '❓')
        print(f"  {icon} {p['slug']:<35} {p['title']:<30} [{p['content_size']}]")

    # HTML
    html_report = generate_html_report(analyzed, wp_url, has_routing)
    output_path = Path(args.output)
    output_path.write_text(html_report, encoding='utf-8')
    print(f"\n✅ Rapport HTML → {output_path.resolve()}")

    if args.json:
        json_path = output_path.with_suffix('.json')
        json_path.write_text(json.dumps(analyzed, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"✅ Données JSON → {json_path.resolve()}")

    print(f"\n💡 Ouvrez {output_path} dans votre navigateur.")


if __name__ == '__main__':
    main()
